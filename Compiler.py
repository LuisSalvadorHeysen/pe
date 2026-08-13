from llvmlite import ir

from AST import Node, NodeType, Program, Expression, Statement
from AST import ExpressionStatement, LetStatement, BlockStatement, FunctionStatement, ReturnStatement, AssignStatement, IfStatement
from AST import WhileStatement, BreakStatement, ContinueStatement, ForStatement
from AST import InfixExpression, PrefixExpression, CallExpression, IndexExpression
from AST import IntegerLiteral, FloatLiteral, IdentifierLiteral, BooleanLiteral, StringLiteral, ArrayLiteral
from AST import FunctionParameter

from Environment import Environment

class Compiler:
    def __init__(self) -> None:
        self.type_map: dict[str, ir.Type] = {
            'int': ir.IntType(32),
            'float': ir.FloatType(),
            'bool': ir.IntType(1),
            'str': ir.IntType(8).as_pointer()
        }

        self.module: ir.Module = ir.Module('main')
        self.builder: ir.IRBuilder = ir.IRBuilder()
        self.env : Environment = Environment()

        self.errors: list[str] = []

        # Stack of (continue_block, break_block) for the loops we are inside of
        self.loops: list[tuple[ir.Block, ir.Block]] = []

        # Cache for printf format string globals ("%d\n" etc.)
        self.fmt_strings: dict[str, ir.GlobalVariable] = {}

        # Cache for string literal globals, keyed by content
        self.strings: dict[str, ir.GlobalVariable] = {}

        self.__initialize_builtins()


    def __initialize_builtins(self) -> None:
        def __init_booleans() -> tuple[ir.GlobalVariable, ir.GlobalVariable]:
            bool_type: ir.Type = self.type_map['bool']

            true_var = ir.GlobalVariable(self.module, bool_type, 'true')
            true_var.initializer = ir.Constant(bool_type, 1)
            true_var.global_constant = True

            false_var = ir.GlobalVariable(self.module, bool_type, 'false')
            false_var.initializer = ir.Constant(bool_type, 0)
            false_var.global_constant = True

            return true_var, false_var
        
        true_var, false_var = __init_booleans()
        self.env.define('true', true_var, true_var.type)
        self.env.define('false', false_var, false_var.type)

        # Declare C's printf so print() has something to call
        printf_type = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()], var_arg=True)
        self.printf = ir.Function(self.module, printf_type, name='printf')

    def compile(self, node: Node) -> None:
        match node.type():
            case NodeType.Program:
                self.__visit_program(node)

            # Statements
            case NodeType.ExpressionStatement:
                self.__visit_expression_statement(node)
            case NodeType.LetStatement:
                self.__visit_let_statement(node)
            case NodeType.FunctionStatement:
                self.__visit_function_statement(node)
            case NodeType.BlockStatement:
                self.__visit_block_statement(node)
            case NodeType.ReturnStatement:
                self.__visit_return_statement(node)
            case NodeType.AssignStatement:
                self.__visit_assign_statement(node)
            case NodeType.IfStatement:
                self.__visit_if_statement(node)
            case NodeType.WhileStatement:
                self.__visit_while_statement(node)
            case NodeType.BreakStatement:
                self.__visit_break_statement(node)
            case NodeType.ContinueStatement:
                self.__visit_continue_statement(node)
            case NodeType.ForStatement:
                self.__visit_for_statement(node)

            case NodeType.InfixExpression:
                self.__visit_infix_expression(node)
            case NodeType.PrefixExpression:
                self.__visit_prefix_expression(node)
            case NodeType.CallExpression:
                self.__visit_call_expression(node)
            
    # region Visit Methods
    def __visit_program(self, node: Program) -> None:
        for stmt in node.statements:
            if stmt.type() != NodeType.FunctionStatement:
                self.errors.append("COMPILE ERROR: only function definitions are allowed at the top level")
                continue

            self.compile(stmt)


    # region Statements
    def __visit_expression_statement(self, node: ExpressionStatement) -> None:
        self.compile(node.expr)  

    def __visit_let_statement(self, node: LetStatement) -> None:
        name: str = node.name.value
        value: Expression = node.value

        value, Type = self.__resolve_value(node=value)

        # If the let has a type annotation, make sure the value matches it.
        # Without one the variable just takes the type of its value.
        if node.value_type is not None and Type != self.type_map[node.value_type]:
            self.errors.append(f"TYPE ERROR line {node.line_no}: '{name}' is declared as {node.value_type} but the value is a {self.__type_name(Type)}")
            return

        if self.env.lookup(name) is None:
            # Define and allocate the value
            ptr = self.builder.alloca(Type)

            # Storing the value to the ptr
            self.builder.store(value, ptr)

            # Add the variable to the environment
            self.env.define(name, ptr, Type)
        else:
            ptr, _ = self.env.lookup(name)
            self.builder.store(value, ptr)
    
    def __visit_block_statement(self, node: BlockStatement) -> None:
        for stmt in node.statements:
            self.compile(stmt)

            # Anything after a return / break / continue is unreachable, skip it
            if self.builder.block is not None and self.builder.block.is_terminated:
                break

    def __visit_return_statement(self, node: ReturnStatement) -> None:
        value: Expression = node.return_value
        value, Type = self.__resolve_value(value)

        expected: ir.Type = self.builder.function.function_type.return_type
        if Type != expected:
            self.errors.append(f"TYPE ERROR line {node.line_no}: function returns {self.__type_name(expected)} but got a {self.__type_name(Type)}")
            return

        self.builder.ret(value)
    
    def __visit_function_statement(self, node: FunctionStatement) -> None:
        name: str = node.name.value
        body: BlockStatement = node.body
        params: list[FunctionParameter] = node.parameters

        param_names: list[str] = [p.name for p in params]

        # Keep track of the types for each parameter
        param_types: list[ir.Type] = [self.type_map[p.value_type] for p in params]

        return_type: ir.Type = self.type_map[node.return_type]

        fnty: ir.FunctionType = ir.FunctionType(return_type, param_types)
        func: ir.Function = ir.Function(self.module, fnty, name=name)

        block: ir.Block = func.append_basic_block(f"{name}_entry")

        previous_builder = self.builder
        
        self.builder = ir.IRBuilder(block)

        # Storing the pointers to each parameter
        params_ptr = []
        for i, typ in enumerate(param_types):
            ptr = self.builder.alloca(typ)
            self.builder.store(func.args[i], ptr)
            params_ptr.append(ptr)

        # Adding the parameters to the environment
        previous_env = self.env

        self.env = Environment(parent=previous_env)
        for i, x in enumerate(zip(param_types, param_names)):
            typ = param_types[i]
            ptr = params_ptr[i]

            self.env.define(x[1], ptr, typ)

        self.env.define(name, func, return_type)

        self.compile(body)

        # If control can fall off the end of the function, return a zero
        # of the right type so every block ends with a terminator
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(return_type, 0.0 if isinstance(return_type, ir.FloatType) else 0))

        self.env = previous_env
        self.env.define(name, func, return_type)

        self.builder = previous_builder

    def __visit_assign_statement(self, node: AssignStatement) -> None:
        value: Expression = node.right_value

        # a[i] = value
        if node.ident.type() == NodeType.IndexExpression:
            entry = self.__resolve_index_ptr(node.ident)
            if entry is None:
                return

            elem_ptr, elem_type = entry
            value, Type = self.__resolve_value(value)

            if Type != elem_type:
                self.errors.append(f"TYPE ERROR line {node.line_no}: array holds {self.__type_name(elem_type)}s, cannot assign a {self.__type_name(Type)}")
                return

            self.builder.store(value, elem_ptr)
            return

        name: str = node.ident.value

        value, Type = self.__resolve_value(value)

        if self.env.lookup(name) is None:
            self.errors.append(f"COMPILE ERROR line {node.line_no}: identifier '{name}' has not been declared before it was assigned to")
            return

        ptr, var_type = self.env.lookup(name)

        if Type != var_type:
            self.errors.append(f"TYPE ERROR line {node.line_no}: '{name}' is a {self.__type_name(var_type)}, cannot assign a {self.__type_name(Type)} to it")
            return

        self.builder.store(value, ptr)

    def __visit_if_statement(self, node: IfStatement) -> None:
        condition = node.condition
        consequence = node.consequence
        alternative = node.alternative

        test, test_type = self.__resolve_value(condition)

        if test_type != ir.IntType(1):
            self.errors.append(f"TYPE ERROR line {node.line_no}: if condition must be a bool, got a {self.__type_name(test_type)}")
            test = ir.Constant(ir.IntType(1), 0)

        if alternative is None:
            with self.builder.if_then(test):
                self.compile(consequence)
        else:
            with self.builder.if_else(test) as (true, otherwise):
                with true:
                    self.compile(consequence)
                with otherwise:
                    self.compile(alternative)

    def __visit_while_statement(self, node: WhileStatement) -> None:
        func: ir.Function = self.builder.function

        cond_block: ir.Block = func.append_basic_block('while_cond')
        body_block: ir.Block = func.append_basic_block('while_body')
        exit_block: ir.Block = func.append_basic_block('while_exit')

        # Jump from the current block into the condition check
        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)

        test, test_type = self.__resolve_value(node.condition)
        if test_type != ir.IntType(1):
            self.errors.append(f"TYPE ERROR line {node.line_no}: while condition must be a bool, got a {self.__type_name(test_type)}")
            test = ir.Constant(ir.IntType(1), 0)

        self.builder.cbranch(test, body_block, exit_block)

        # break/continue inside the body need to know where to jump to
        self.loops.append((cond_block, exit_block))

        self.builder.position_at_start(body_block)
        self.compile(node.body)

        # Loop back to the condition, unless the body already jumped somewhere
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_block)

        self.loops.pop()

        self.builder.position_at_start(exit_block)

    def __visit_break_statement(self, node: BreakStatement) -> None:
        if len(self.loops) == 0:
            self.errors.append(f"COMPILE ERROR line {node.line_no}: 'break' used outside of a loop")
            return

        cond_block, exit_block = self.loops[-1]
        self.builder.branch(exit_block)

    def __visit_continue_statement(self, node: ContinueStatement) -> None:
        if len(self.loops) == 0:
            self.errors.append(f"COMPILE ERROR line {node.line_no}: 'continue' used outside of a loop")
            return

        cond_block, exit_block = self.loops[-1]
        self.builder.branch(cond_block)

    def __visit_for_statement(self, node: ForStatement) -> None:
        func: ir.Function = self.builder.function

        cond_block: ir.Block = func.append_basic_block('for_cond')
        body_block: ir.Block = func.append_basic_block('for_body')
        post_block: ir.Block = func.append_basic_block('for_post')
        exit_block: ir.Block = func.append_basic_block('for_exit')

        # The init runs once, in the current block
        self.compile(node.init)
        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)

        test, test_type = self.__resolve_value(node.condition)
        if test_type != ir.IntType(1):
            self.errors.append(f"TYPE ERROR line {node.line_no}: for condition must be a bool, got a {self.__type_name(test_type)}")
            test = ir.Constant(ir.IntType(1), 0)

        self.builder.cbranch(test, body_block, exit_block)

        # continue jumps to the post step, break jumps out
        self.loops.append((post_block, exit_block))

        self.builder.position_at_start(body_block)
        self.compile(node.body)

        if not self.builder.block.is_terminated:
            self.builder.branch(post_block)

        self.loops.pop()

        self.builder.position_at_start(post_block)
        self.compile(node.post)
        self.builder.branch(cond_block)

        self.builder.position_at_start(exit_block)

    # endregion

    # region Expressions
    def __visit_infix_expression(self, node: InfixExpression) -> None:
        operator: str = node.operator
        left_value, left_type = self.__resolve_value(node.left_node)
        right_value, right_type = self.__resolve_value(node.right_node)

        if left_type != right_type:
            self.errors.append(f"TYPE ERROR line {node.line_no}: cannot use '{operator}' on a {self.__type_name(left_type)} and a {self.__type_name(right_type)}")
            return ir.Constant(self.type_map['int'], 0), self.type_map['int']

        value = None
        Type = None

        # Booleans only support == and !=
        if left_type == ir.IntType(1):
            match operator:
                case '==':
                    value = self.builder.icmp_signed('==', left_value, right_value)
                case '!=':
                    value = self.builder.icmp_signed('!=', left_value, right_value)

            if value is None:
                self.errors.append(f"TYPE ERROR line {node.line_no}: cannot use '{operator}' on bools")
                return ir.Constant(self.type_map['int'], 0), self.type_map['int']

            return value, ir.IntType(1)

        if isinstance(right_type, ir.IntType) and isinstance(left_type, ir.IntType):
            Type = self.type_map['int']
            match operator:
                case '+':
                    value = self.builder.add(left_value, right_value)
                case '-':
                    value = self.builder.sub(left_value, right_value)
                case '*':
                    value = self.builder.mul(left_value, right_value)
                case '/':
                    value = self.builder.sdiv(left_value, right_value)
                case '%':
                    value = self.builder.srem(left_value, right_value)
                case '<':
                    value = self.builder.icmp_signed('<', left_value, right_value)
                    Type = ir.IntType(1)
                case '<=':
                    value = self.builder.icmp_signed('<=', left_value, right_value)
                    Type = ir.IntType(1)
                case '>':
                    value = self.builder.icmp_signed('>', left_value, right_value)
                    Type = ir.IntType(1)
                case '>=':
                    value = self.builder.icmp_signed('>=', left_value, right_value)
                    Type = ir.IntType(1)
                case '==':
                    value = self.builder.icmp_signed('==', left_value, right_value)
                    Type = ir.IntType(1)
                case '!=':
                    value = self.builder.icmp_signed('!=', left_value, right_value)
                    Type = ir.IntType(1)

        if isinstance(right_type, ir.FloatType) and isinstance(left_type, ir.FloatType):
            Type = self.type_map['float']
            match operator:
                case '+':
                    value = self.builder.fadd(left_value, right_value)
                case '-':
                    value = self.builder.fsub(left_value, right_value)
                case '*':
                    value = self.builder.fmul(left_value, right_value)
                case '/':
                    value = self.builder.fdiv(left_value, right_value)
                case '%':
                    value = self.builder.frem(left_value, right_value)
                case '<':
                    value = self.builder.fcmp_ordered('<', left_value, right_value)
                    Type = ir.IntType(1)
                case '<=':
                    value = self.builder.fcmp_ordered('<=', left_value, right_value)
                    Type = ir.IntType(1)
                case '>':
                    value = self.builder.fcmp_ordered('>', left_value, right_value)
                    Type = ir.IntType(1)
                case '>=':
                    value = self.builder.fcmp_ordered('>=', left_value, right_value)
                    Type = ir.IntType(1)
                case '==':
                    value = self.builder.fcmp_ordered('==', left_value, right_value)
                    Type = ir.IntType(1)   
                case '!=':
                    value = self.builder.fcmp_ordered('!=', left_value, right_value)
                    Type = ir.IntType(1)

        if value is None:
            self.errors.append(f"COMPILE ERROR line {node.line_no}: operator '{operator}' is not supported for {self.__type_name(left_type)}s")
            return ir.Constant(self.type_map['int'], 0), self.type_map['int']

        return value, Type

    def __visit_prefix_expression(self, node: PrefixExpression) -> tuple[ir.Value, ir.Type]:
        value, Type = self.__resolve_value(node.right_node)

        match node.operator:
            case '-':
                if isinstance(Type, ir.FloatType):
                    return self.builder.fneg(value), Type
                if Type == ir.IntType(1):
                    self.errors.append(f"TYPE ERROR line {node.line_no}: cannot negate a bool")
                    return ir.Constant(self.type_map['int'], 0), self.type_map['int']
                return self.builder.neg(value), Type

        self.errors.append(f"COMPILE ERROR line {node.line_no}: unknown prefix operator '{node.operator}'")
        return ir.Constant(self.type_map['int'], 0), self.type_map['int']

    def __visit_call_expression(self, node: CallExpression) -> tuple[ir.Instruction, ir.Type]:
        name: str = node.function.value
        params: list[Expression] = node.arguments

        args = []
        types = []

        if len(params) > 0:
            for x in params:
                p_val, p_type = self.__resolve_value(x)
                args.append(p_val)
                types.append(p_type)

        match name:
            case 'print' | 'habla':
                ret = self.__builtin_print(args, types, node)
                ret_type = self.type_map['int']
            case 'len':
                # len(a) for arrays; the size is known at compile time
                if len(types) != 1 or not isinstance(types[0], ir.ArrayType):
                    self.errors.append(f"COMPILE ERROR line {node.line_no}: len() takes one array argument")
                    return ir.Constant(self.type_map['int'], 0), self.type_map['int']

                ret = ir.Constant(self.type_map['int'], types[0].count)
                ret_type = self.type_map['int']
            case _:
                entry = self.env.lookup(name)
                if entry is None:
                    self.errors.append(f"COMPILE ERROR line {node.line_no}: undefined function '{name}'")
                    return ir.Constant(self.type_map['int'], 0), self.type_map['int']

                func, ret_type = entry

                if len(args) != len(func.args):
                    self.errors.append(f"COMPILE ERROR line {node.line_no}: '{name}' takes {len(func.args)} argument(s), got {len(args)}")
                    return ir.Constant(self.type_map['int'], 0), self.type_map['int']

                ret = self.builder.call(func, args)

        return ret, ret_type

    # endregion

    # endregion

    # region Helper Methods
    def __type_name(self, Type: ir.Type) -> str:
        """ Turns an LLVM type back into a PE++ type name for error messages """
        if isinstance(Type, ir.FloatType):
            return 'float'
        if isinstance(Type, ir.IntType) and Type.width == 1:
            return 'bool'
        if isinstance(Type, ir.IntType):
            return 'int'
        if isinstance(Type, ir.PointerType):
            return 'str'
        if isinstance(Type, ir.ArrayType):
            return f'{self.__type_name(Type.element)}[{Type.count}]'
        return str(Type)

    def __fmt_string(self, name: str, text: str) -> ir.Value:
        """ Gets (or creates) a global constant like "%d\n" for printf """
        if name not in self.fmt_strings:
            data = bytearray(text.encode('utf8') + b'\x00')
            typ = ir.ArrayType(ir.IntType(8), len(data))

            g = ir.GlobalVariable(self.module, typ, name)
            g.initializer = ir.Constant(typ, data)
            g.global_constant = True

            self.fmt_strings[name] = g

        return self.builder.bitcast(self.fmt_strings[name], ir.IntType(8).as_pointer())

    def __builtin_print(self, args: list[ir.Value], types: list[ir.Type], node: CallExpression) -> ir.Value:
        """ print(a, b, ...) -> one printf call per argument, one line each """
        ret = ir.Constant(self.type_map['int'], 0)

        for value, typ in zip(args, types):
            if isinstance(typ, ir.FloatType):
                fmt = self.__fmt_string('fmt_float', '%g\n')
                # varargs promote floats to doubles in C, printf expects that
                value = self.builder.fpext(value, ir.DoubleType())
            elif isinstance(typ, ir.PointerType):
                fmt = self.__fmt_string('fmt_str', '%s\n')
            elif isinstance(typ, ir.IntType):
                fmt = self.__fmt_string('fmt_int', '%d\n')
                if typ.width == 1:
                    value = self.builder.zext(value, self.type_map['int'])
            else:
                self.errors.append(f"TYPE ERROR line {node.line_no}: cannot print a {self.__type_name(typ)}")
                continue

            ret = self.builder.call(self.printf, [fmt, value])

        return ret

    def __resolve_index_ptr(self, node: IndexExpression) -> tuple[ir.Value, ir.Type]:
        """ a[i] -> a pointer to the element, via GEP. Returns None on error. """
        if node.left.type() != NodeType.IdentifierLiteral:
            self.errors.append(f"COMPILE ERROR line {node.line_no}: only variables can be indexed")
            return None

        name: str = node.left.value

        entry = self.env.lookup(name)
        if entry is None:
            self.errors.append(f"COMPILE ERROR line {node.line_no}: undefined variable '{name}'")
            return None

        ptr, Type = entry
        if not isinstance(Type, ir.ArrayType):
            self.errors.append(f"TYPE ERROR line {node.line_no}: '{name}' is a {self.__type_name(Type)}, not an array")
            return None

        idx_value, idx_type = self.__resolve_value(node.index)
        if idx_type != self.type_map['int']:
            self.errors.append(f"TYPE ERROR line {node.line_no}: array index must be an int, got a {self.__type_name(idx_type)}")
            return None

        # Catch out-of-bounds indexes at compile time when the index is a literal
        if node.index.type() == NodeType.IntegerLiteral:
            if node.index.value < 0 or node.index.value >= Type.count:
                self.errors.append(f"COMPILE ERROR line {node.line_no}: index {node.index.value} is out of bounds for '{name}' ({self.__type_name(Type)})")
                return None

        zero = ir.Constant(self.type_map['int'], 0)
        elem_ptr = self.builder.gep(ptr, [zero, idx_value], inbounds=True)

        return elem_ptr, Type.element

    def __resolve_value(self, node: Expression, value_type: str = None) -> tuple[ir.Value, ir.Type]:
        match node.type():
            case NodeType.IntegerLiteral:
               node: IntegerLiteral = node
               value, Type = node.value, self.type_map['int' if value_type is None else value_type]
               return ir.Constant(Type, value), Type
            case NodeType.FloatLiteral:
               node: FloatLiteral = node
               value, Type = node.value, self.type_map['float' if value_type is None else value_type]
               return ir.Constant(Type, value), Type
            case NodeType.IdentifierLiteral:
               node: IdentifierLiteral = node
               entry = self.env.lookup(node.value)
               if entry is None:
                   self.errors.append(f"COMPILE ERROR line {node.line_no}: undefined variable '{node.value}'")
                   return ir.Constant(self.type_map['int'], 0), self.type_map['int']

               ptr, Type = entry
               return self.builder.load(ptr), Type
            case NodeType.BooleanLiteral:
               node: BooleanLiteral = node
               return ir.Constant(ir.IntType(1), 1 if node.value else 0), ir.IntType(1)
            case NodeType.StringLiteral:
               node: StringLiteral = node
               if node.value not in self.strings:
                   data = bytearray(node.value.encode('utf8') + b'\x00')
                   typ = ir.ArrayType(ir.IntType(8), len(data))

                   g = ir.GlobalVariable(self.module, typ, f'str.{len(self.strings)}')
                   g.initializer = ir.Constant(typ, data)
                   g.global_constant = True

                   self.strings[node.value] = g

               ptr = self.builder.bitcast(self.strings[node.value], self.type_map['str'])
               return ptr, self.type_map['str']
            case NodeType.ArrayLiteral:
               node: ArrayLiteral = node
               if len(node.elements) == 0:
                   self.errors.append(f"COMPILE ERROR line {node.line_no}: empty array literals are not allowed (no way to know the type)")
                   return ir.Constant(self.type_map['int'], 0), self.type_map['int']

               values = []
               elem_type = None
               for elem in node.elements:
                   v, t = self.__resolve_value(elem)
                   if elem_type is None:
                       elem_type = t
                   elif t != elem_type:
                       self.errors.append(f"TYPE ERROR line {node.line_no}: array elements must all be the same type ({self.__type_name(elem_type)} vs {self.__type_name(t)})")
                       return ir.Constant(self.type_map['int'], 0), self.type_map['int']
                   values.append(v)

               arr_type = ir.ArrayType(elem_type, len(values))

               # Build the aggregate value one element at a time
               agg = ir.Constant(arr_type, ir.Undefined)
               for i, v in enumerate(values):
                   agg = self.builder.insert_value(agg, v, i)

               return agg, arr_type
            case NodeType.IndexExpression:
                entry = self.__resolve_index_ptr(node)
                if entry is None:
                    return ir.Constant(self.type_map['int'], 0), self.type_map['int']

                elem_ptr, elem_type = entry
                return self.builder.load(elem_ptr), elem_type
            # Expression Values
            case NodeType.InfixExpression:
                return self.__visit_infix_expression(node)
            case NodeType.PrefixExpression:
                return self.__visit_prefix_expression(node)
            case NodeType.CallExpression:
                return self.__visit_call_expression(node)

    # endregion