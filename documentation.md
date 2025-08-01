# Peruvian Programming Language Documentation

This document outlines the syntax and features of the Peruvian Programming Language.

## Comments

The language currently does not support comments.

## Data Types

- **Integer:** `int` (e.g., `10`, `25`, `100`)
- **Float:** `float` (e.g., `3.14`, `2.71`, `1.0`)
- **Boolean:** `bool` (e.g., `alafirme`, `floro`)

## Keywords

- `let` or `dale`: Used for variable declaration.
- `sipe`: Used as a statement terminator, completely equivalent to a semicolon (`;`). If `sipe` is used, a semicolon is not needed, and vice-versa.
- `alafirme`: Represents the boolean value `true`.
- `floro`: Represents the boolean value `false`.
- `if`: Used for conditional statements.
- `else`: Used with `if` for alternative execution paths.
- `return`: Used to return a value from a function.
- `fn`: Used to define a function.

## Operators

### Arithmetic Operators

- `+`: Addition
- `-`: Subtraction
- `*`: Multiplication
- `/`: Division
- `^`: Exponentiation
- `%`: Modulus

### Logical Operators

- `!`: Logical NOT
- `&&`: Logical AND
- `||`: Logical OR

### Comparison Operators

- `==`: Equal to
- `!=`: Not equal to
- `<`: Less than
- `>`: Greater than

## Variable Declaration

Variables are declared using the `let` or `dale` keyword, followed by the variable name, type, and value.

### Syntax

```
let <variable_name>: <type> = <value>;
dale <variable_name>: <type> = <value> sipe;
```

### Examples

```
let x: int = 5;
dale y: float = 3.14 sipe;
let is_peruvian: bool = alafirme;
```

## Code Blocks

Code blocks are defined using curly braces `{}`. Whitespace (spaces, tabs, newlines) is ignored by the lexer, allowing for flexible formatting.

## Conditional Statements (if/else)

Conditional statements allow for different code execution paths based on a boolean condition.

### Syntax

```
if (<condition>) {
    // code to execute if condition is alafirme
} else {
    // code to execute if condition is floro
}
```

### Examples

```
if (x > 10) {
    let result: int = 1;
} else {
    let result: int = 0;
}

if (is_peruvian) {
    // do something
}
```

## Return Statements

Return statements are used to exit a function and return a value.

### Syntax

```
return <expression>;
```

### Examples

```
return x + y;
return alafirme;
```

## Function Definitions

Functions are defined using the `fn` keyword, followed by the function name, parameters, return type, and a code block.

### Syntax

```
fn <function_name>(<parameter1_name>: <parameter1_type>, ...) <return_type> {
    // function body
}
```

### Examples

```
fn add(a: int, b: int) int {
    return a + b;
}

fn greet() bool {
    return alafirme;
}
```

## Function Calls

Functions are called by their name followed by arguments in parentheses.

### Syntax

```
<function_name>(<argument1>, <argument2>, ...)
```

### Examples

```
let sum: int = add(5, 10);
let greeting_status: bool = greet();
```