# PE++

A small statically typed language compiled to native code through LLVM — with optional Peruvian slang keywords.

```
casera main() bota int {
    pucha sum ponle 0 pe
    pucha i ponle 1 pe

    dale i <= 10 {
        sum ponle sum + i pe
        i ponle i + 1 pe
    }

    habla(sum) pe          // prints 55
    tomacausa sum pe
}
```

Every keyword also has a standard spelling (`fn`, `let`, `while`, `return`, ...) — see the [keyword table](#the-slang-keywords) below.

## Architecture

```
source (.pe)
   │
   ▼
Lexer ──────────── tokens (with line/column info)
   │
   ▼
Parser ─────────── AST          Pratt parser (top-down operator precedence)
   │
   ▼
Compiler ───────── LLVM IR      type checking + IR generation over the AST,
   │                            scoped symbol tables, basic-block generation
   ▼                            for control flow
Optimization ───── LLVM IR      mem2reg (SROA), constant folding,
   │                            SCCP, DCE, CFG simplification
   ▼
MCJIT execution  or  object file + cc link → native executable
```

- **`Lexer.py`** turns source text into tokens, tracking line and column for error messages.
- **`Parser.py`** is a Pratt parser producing the AST in `AST.py`. Syntax errors are collected with locations, not thrown.
- **`Compiler.py`** walks the AST and emits LLVM IR via [llvmlite](https://llvmlite.readthedocs.io/). Variables live in `alloca` slots (the mem2reg pass promotes them to SSA registers later). `if`, `while` and `for` compile to explicit basic blocks with conditional branches; `break`/`continue` jump to the exit/step block of the innermost loop. Arrays are stack-allocated aggregates indexed with GEP instructions, with compile-time bounds checks for constant indexes; strings are pointers into global constants. Type checking happens here too — every expression resolves to `(value, type)` and mismatches are reported with line numbers.
- **`main.py`** drives the pipeline: verify the IR, run the optimization passes, then either JIT-execute it, print it, or emit an object file and link it with the system C compiler.

## Quick start

Requires Python 3.10+ and a C compiler (`cc`) for native builds.

```bash
pip install -r requirements.txt

# JIT-compile and run
python main.py examples/fib.pe

# Compile to a native executable
python main.py examples/fib.pe -o fib
./fib

# Look at the LLVM IR
python main.py examples/fib.pe --emit-ir            # optimized
python main.py examples/fib.pe --emit-ir --no-opt   # raw codegen output
```

## What the optimizer does

The compiler intentionally generates naive IR (every variable is a stack slot) and lets LLVM clean it up. For this function:

```
fn add(a: int, b: int) -> int {
    let unused = 99;
    return a + b;
}
```

raw codegen output (`--no-opt`):

```llvm
define i32 @add(i32 %.1, i32 %.2) {
add_entry:
  %.4 = alloca i32, align 4
  store i32 %.1, i32* %.4, align 4
  %.6 = alloca i32, align 4
  store i32 %.2, i32* %.6, align 4
  %.8 = alloca i32, align 4
  store i32 99, i32* %.8, align 4
  %.10 = load i32, i32* %.4, align 4
  %.11 = load i32, i32* %.6, align 4
  %.12 = add i32 %.10, %.11
  ret i32 %.12
}
```

after the pass pipeline (SROA/mem2reg, instruction combining, SCCP, DCE, CFG simplification):

```llvm
define i32 @add(i32 %.1, i32 %.2) {
add_entry:
  %.12 = add i32 %.1, %.2
  ret i32 %.12
}
```

The stack slots are promoted to SSA registers and the dead `unused` variable disappears.

## Language tour

```
// Comments run to the end of the line.

// Functions declare parameter and return types.
fn add(a: int, b: int) -> int {
    return a + b;
}

fn main() -> int {
    let a: int = 5;        // explicit type
    let b = 7;             // type inferred from the value

    // if / else
    if a < b {
        a = a + 1;
    } else {
        a = a - 1;
    }

    // while, break, continue
    let i = 0;
    while i < 10 {
        i = i + 1;
        if i % 2 == 0 {
            continue;
        }
        if i > 7 {
            break;
        }
    }

    // for loops: init; condition; step
    for let k = 0; k < 5; k = k + 1 {
        i = i + k;
    }

    // fixed-size arrays with inferred element types,
    // indexed reads/writes, and a compile-time len()
    let nums = [10, 20, 30];
    nums[1] = 25;
    let total = 0;
    for let k = 0; k < len(nums); k = k + 1 {
        total = total + nums[k];
    }

    // strings
    let saludo: str = "hola causa";

    // print takes any number of ints, floats, bools or strings
    print(a, 2.5, a < b, saludo);

    return add(a, b);
}
```

Types: `int` (i32), `float` (f32), `bool`, `str`, and fixed-size arrays like `int[3]` (created from literals, element type inferred). Operators: `+ - * / %`, comparisons `< <= > >= == !=`, unary `-`, indexing `a[i]`.

## Error reporting

Errors are reported with source locations instead of Python tracebacks:

```
$ python main.py bad.pe
TYPE ERROR line 2: 'a' is declared as int but the value is a float
COMPILE ERROR line 3: undefined variable 'b'
COMPILE ERROR line 4: index 5 is out of bounds for 'nums' (int[3])
```

```
$ python main.py bad2.pe
SYNTAX ERROR line 3, column 5: expected SEMICOLON, got RETURN ('return')
```

## Tests

83 test cases covering execution results, printed output, syntax errors, and type/compile errors:

```bash
python run_tests.py
# ...
# 83/83 tests passed
```

Each test declares its expectations in header comments (`// expect: 42`, `// out: hello`, `// error: undefined variable`), and the runner executes it through the real compiler. CI runs the suite plus a native-binary build on every push.

## The slang keywords

PE++ started as a tribute to Peruvian Independence Day, so every keyword has a Peruvian slang alternative. Both spellings work anywhere, and they can be mixed freely:

| slang        | standard   | meaning                     |
|--------------|------------|-----------------------------|
| `pucha`      | `let`      | variable declaration        |
| `ponle`      | `=`        | assignment                  |
| `pe`         | `;`        | statement terminator        |
| `casera`     | `fn`       | function declaration        |
| `tomacausa`  | `return`   | return                      |
| `bota`       | `->`       | return type arrow           |
| `sipe`       | `if`       | if                          |
| `sinope`     | `else`     | else                        |
| `dale`       | `while`    | while loop                  |
| `pa`         | `for`      | for loop                    |
| `corta`      | `break`    | break                       |
| `sigue`      | `continue` | continue                    |
| `habla`      | `print`    | print                       |

See `examples/` for full programs in both styles.

## Project layout

```
Lexer.py        tokenizer
Token.py        token types + keyword tables
Parser.py       Pratt parser
AST.py          AST node definitions
Compiler.py     type checking + LLVM IR generation
Environment.py  scoped symbol table
main.py         CLI driver (run / build / emit-ir)
run_tests.py    test runner
tests/cases/    test suite
examples/       sample programs
```

## License

MIT
