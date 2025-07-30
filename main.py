from Lexer import Lexer
from Parser import Parser
from AST import Program
import json
from Compiler import Compiler

from llvmlite import ir
import llvmlite.binding as llvm
from ctypes import CFUNCTYPE, c_int, c_float

LEXER_DEBUG: bool = True
PARSER_DEBUG: bool = False
COMPILER_DEBUG: bool = False

if __name__ == "__main__":
    with open("tests/compiler.pe") as f:
        code: str = f.read()

    if LEXER_DEBUG:

        debug_lex: Lexer = Lexer(source=code)
        while debug_lex.current_char is not None:
            print(debug_lex.next_token())


    l: Lexer = Lexer(source=code)
    p: Parser = Parser(lexer=l) 

    program: Program = p.parse_program()
    if len(p.errors) > 0:
        print("Parser errors:")
        for error in p.errors:
            print(f"  {error}")
        exit(1)


    if PARSER_DEBUG:
        print("Parser Debug Mode:")

        if p.errors:
            print("Parser errors:")
            for error in p.errors:
                print(f"  {error}")
        else:
            print("No parser errors!")

        with open("debug/ast.json", "w") as f:
            json.dump(program.json(), f, indent=4)

        print("AST was saved to debug/ast.json")

    c: Compiler = Compiler()
    c.compile(node=program)

    # Output steps
    module: ir.Module = c.module
    module.triple = llvm.get_default_triple()

    if COMPILER_DEBUG:
        with open("debug/ir.ll", "w") as f:
            f.write(str(module))