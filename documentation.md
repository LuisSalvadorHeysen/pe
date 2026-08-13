# PE++ Language Reference

The README covers the compiler architecture and a quick tour; this is the full language reference.

## Comments

```
// comments run to the end of the line
```

## Data types

| type     | LLVM type   | examples              |
|----------|-------------|-----------------------|
| `int`    | `i32`       | `10`, `-3`            |
| `float`  | `float`     | `3.14`, `1.0`         |
| `bool`   | `i1`        | `true`, `false`       |
| `str`    | `i8*`       | `"hola"`, `"a\nb"`    |
| arrays   | `[N x T]`   | `[1, 2, 3]`, `[1.5, 2.5]` |

Types never convert implicitly — mixing an `int` and a `float` in one expression is a compile-time type error.

String literals support the escapes `\n`, `\t`, `\"` and `\\`. Arrays are fixed-size, one-dimensional, and always created from a literal (the element type and length are inferred from it).

## Keywords

Every keyword has a standard spelling and a Peruvian slang spelling. They are interchangeable everywhere:

| standard   | slang       |
|------------|-------------|
| `let`      | `pucha`     |
| `=`        | `ponle`     |
| `;`        | `pe`        |
| `fn`       | `casera`    |
| `return`   | `tomacausa` |
| `->`       | `bota`      |
| `if`       | `sipe`      |
| `else`     | `sinope`    |
| `while`    | `dale`      |
| `for`      | `pa`        |
| `break`    | `corta`     |
| `continue` | `sigue`     |
| `print`    | `habla`     |

## Operators

- Arithmetic: `+  -  *  /  %` (both operands must have the same type)
- Comparison: `==  !=  <  <=  >  >=` (produce a `bool`; bools themselves only support `==` and `!=`)
- Unary: `-` (negation of ints and floats)
- Indexing: `a[i]` (arrays only; the index must be an `int`)

## Variables

```
let x: int = 5;      // with a type annotation (checked against the value)
let y = 3.14;        // type inferred from the value
x = x + 1;           // assignment; the new value must match the variable's type
```

## Control flow

Conditions must be `bool`s — `if 1 { ... }` is a type error.

```
if x > 10 {
    ...
} else {
    ...
}

while x < 100 {
    if x == 50 {
        break;       // jump out of the loop
    }
    if x % 2 == 0 {
        continue;    // jump back to the condition
    }
    x = x + 1;
}

// for loops: init; condition; step
for let i = 0; i < 10; i = i + 1 {
    ...
}

// the init can also reuse an existing variable
for i = 0; i < 10; i = i + 1 {
    ...
}
```

In a `for` loop, `continue` jumps to the step (`i = i + 1`), not straight to the condition.

## Functions

Programs are a list of function definitions; execution starts at `main() -> int`. Recursion works.

```
fn add(a: int, b: int) -> int {
    return a + b;
}

fn main() -> int {
    return add(5, 10);
}
```

A function that falls off the end without returning produces a zero of its return type.

## Arrays

```
let nums = [10, 20, 30];     // type is int[3], inferred from the literal
nums[1] = 25;                // indexed writes
let x = nums[0] + nums[1];   // indexed reads
let n = len(nums);           // length, resolved at compile time
```

Out-of-bounds constant indexes (`nums[5]`) are compile-time errors. Runtime indexes are not bounds-checked. Arrays cannot be passed to functions or printed.

## Strings

```
let s: str = "hola";
let t = "con\tescapes\n";
print(s);
```

Strings are immutable pointers to global constants. They can be bound to variables, passed to and returned from functions, and printed — there is no concatenation or comparison yet.

## Printing

`print` (slang: `habla`) is a builtin backed by C's `printf`. It accepts any number of ints, floats, bools or strings and prints each on its own line. Bools print as `1`/`0`.

```
print(42, 3.5, 1 < 2, "hola");
```

`len(a)` is the other builtin: the length of an array, as an `int` constant.

## Errors

The compiler reports syntax errors, undefined names, and type mismatches with source locations:

```
SYNTAX ERROR line 3, column 5: expected SEMICOLON, got RETURN ('return')
TYPE ERROR line 2: 'a' is declared as int but the value is a float
COMPILE ERROR line 3: undefined variable 'b'
```
