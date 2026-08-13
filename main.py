import argparse
import ctypes
import json
import os
import subprocess
import sys

from Lexer import Lexer
from Parser import Parser
from Compiler import Compiler
from AST import Program

import llvmlite.binding as llvm
from ctypes import CFUNCTYPE, c_int


def compile_source(path: str, debug: bool = False) -> str:
    """ Source file -> LLVM IR (as text). Prints errors and exits if anything is wrong. """
    with open(path, "r") as f:
        code: str = f.read()

    l: Lexer = Lexer(source=code)
    p: Parser = Parser(lexer=l)
    program: Program = p.parse_program()

    if len(p.errors) > 0:
        for err in p.errors:
            print(err, file=sys.stderr)
        sys.exit(1)

    if debug:
        os.makedirs("debug", exist_ok=True)
        with open("debug/ast.json", "w") as f:
            json.dump(program.json(), f, indent=4)

    c: Compiler = Compiler()
    c.compile(node=program)

    if len(c.errors) > 0:
        for err in c.errors:
            print(err, file=sys.stderr)
        sys.exit(1)

    module = c.module
    module.triple = llvm.get_default_triple()

    return str(module)


def optimize(mod_ref: llvm.ModuleRef) -> None:
    """ The optimization pipeline: mem2reg, constant folding, DCE, CFG cleanup """
    pm = llvm.create_module_pass_manager()
    pm.add_sroa_pass()                    # mem2reg: promote allocas to SSA registers
    pm.add_instruction_combining_pass()   # constant folding + peephole simplifications
    pm.add_sccp_pass()                    # sparse conditional constant propagation
    pm.add_dead_code_elimination_pass()   # drop instructions nobody uses
    pm.add_cfg_simplification_pass()      # merge/remove trivial basic blocks
    pm.run(mod_ref)


def build_module(args) -> llvm.ModuleRef:
    ir_text: str = compile_source(args.file, debug=args.debug)

    try:
        mod_ref = llvm.parse_assembly(ir_text)
        mod_ref.verify()
    except Exception as e:
        print(f"INTERNAL ERROR: compiler produced invalid IR:\n{e}", file=sys.stderr)
        sys.exit(1)

    if not args.no_opt:
        optimize(mod_ref)

    if args.debug:
        os.makedirs("debug", exist_ok=True)
        with open("debug/ir.ll", "w") as f:
            f.write(str(mod_ref))

    return mod_ref


def run_jit(mod_ref: llvm.ModuleRef) -> int:
    """ JIT-compile the module and call its main() """
    try:
        mod_ref.get_function("main")
    except NameError:
        print("COMPILE ERROR: no 'main' function defined", file=sys.stderr)
        sys.exit(1)

    target_machine = llvm.Target.from_default_triple().create_target_machine()

    engine = llvm.create_mcjit_compiler(mod_ref, target_machine)
    engine.finalize_object()

    entry = engine.get_function_address("main")
    cfunc = CFUNCTYPE(c_int)(entry)

    result = cfunc()

    # printf writes through C's stdio buffer, flush it so output
    # shows up before ours
    ctypes.CDLL(None).fflush(None)

    return result


def build_native(mod_ref: llvm.ModuleRef, output: str) -> None:
    """ Module -> object file -> executable (linked with the system C compiler) """
    # reloc='pic' so the object links cleanly into a position-independent executable
    target_machine = llvm.Target.from_default_triple().create_target_machine(opt=2, reloc="pic")

    obj_path = output + ".o"
    with open(obj_path, "wb") as f:
        f.write(target_machine.emit_object(mod_ref))

    link = subprocess.run(["cc", obj_path, "-o", output])
    os.remove(obj_path)

    if link.returncode != 0:
        print("LINK ERROR: cc failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="The PE++ compiler")
    arg_parser.add_argument("file", help="the .pe source file")
    arg_parser.add_argument("-o", "--output", help="compile to a native executable instead of running")
    arg_parser.add_argument("--emit-ir", action="store_true", help="print the LLVM IR and exit")
    arg_parser.add_argument("--no-opt", action="store_true", help="skip the optimization passes")
    arg_parser.add_argument("--debug", action="store_true", help="dump the AST and IR into debug/")
    args = arg_parser.parse_args()

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    mod_ref = build_module(args)

    if args.emit_ir:
        print(str(mod_ref))
    elif args.output is not None:
        build_native(mod_ref, args.output)
        print(f"Wrote {args.output}")
    else:
        result = run_jit(mod_ref)
        print(f"Program returned: {result}")
