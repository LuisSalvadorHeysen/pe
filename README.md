# PE++ - A Statically Typed Compiled Language with Peruvian Slang

PE++ is a statically typed compiled language built as a tribute to Peruvian Independence Day. It features Peruvian slang words as keywords, providing a unique programming experience that celebrates Peruvian culture.

## Language Overview

PE++ offers both standard programming keywords and alternative Peruvian slang keywords that map to the same functionality. This allows developers to write code in a traditional style or embrace the Peruvian-inspired syntax.

## Keyword Mappings

### Standard Keywords
```python
KEYWORDS: dict[str, TokenType] = {
    "let": TokenType.LET,
    "fn": TokenType.FN,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
}
```

### Alternative Peruvian Slang Keywords
```python
ALT_KEYWORDS: dict[str, TokenType] = {
    "pucha": TokenType.LET,
    "ponle": TokenType.EQ,
    "pe": TokenType.SEMICOLON,
    "casera": TokenType.FN,
    "tomacausa": TokenType.RETURN,
    "aquisitonoma": TokenType.ARROW,
    "sipe": TokenType.IF,
    "sinope": TokenType.ELSE
}
```

## Example Code with Standard Syntax

```python
fn add(a: int, b: int) -> int {
    return a + b;
}

fn main() -> int {
    let a: int = 5;

    if a == 5 {
        return add(10, 5);
    } else {
        return add(10, 1);
    }

    return 0;
}
```

## Example Code with Peruvian Slang Keywords

```
casera add(a: int, b: int) bota int {
    tomacausa a + b pe
}

casera main() bota int {
    pucha a: int ponle 5 pe

    sipe a == 5 {
        tomacausa add(10, 5) pe
    } sinope {
        tomacausa add(10, 1) pe
    }

    tomacausa 0 pe
}
```

## Keyword Meanings

- **pucha**: Used for variable declarations (equivalent to "let")
- **ponle**: Assignment operator (equivalent to "=")
- **pe**: Statement terminator (equivalent to ";")
- **casera**: Function declaration keyword (equivalent to "fn")
- **tomacausa**: Return statement (equivalent to "return")
- **bota**: Arrow operator for return types (equivalent to "->")
- **sipe**: Conditional statement (equivalent to "if")
- **sinope**: Alternative branch (equivalent to "else")
