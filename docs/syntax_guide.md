# The Kinetic Syntax Guide

This guide describes the 1.2.2 prototype. Kinetic explores readable systems-language syntax, but it does not yet provide a production memory-safety model.

Kinetic uses concise declarations and compiles through LLVM. The examples below
show current syntax, not the proposed bootstrap host-service API.

See the [documentation index](README.md) for installation and architecture guides.

## Declaration keywords

| Purpose | Keyword |
| --- | --- |
| Define a function | [`func`](../compiler/lexer.py:33) |
| Declare an immutable binding | [`let`](../compiler/lexer.py:34) |
| Declare a mutable binding | [`mut`](../compiler/lexer.py:35) |

Declaring a name, reassigning a value, and calling a function are separate
operations. A mutable declaration starts directly with its own keyword.

## 1. Variables (and why they are strict)

An immutable binding gives a name to a value and cannot be reassigned. Types are inferred from expressions; you do not need a type annotation.

```text
// The compiler automatically figures out `name` is a String and `age` is an Int.
let name = "Aspyron"
let age = 5
```

For a binding that can be reassigned, use [`mut`](../compiler/lexer.py:35) as the declaration keyword:

```text
mut counter = 0
counter = counter + 1 // Reassignment has no declaration keyword.
```

Binding immutability is not a general guarantee that referenced data is deeply
immutable or memory-safe. Version 1.2.2 supports integer-array reads, but does not implement
indexed assignment or a production memory-safety model.

## 2. Functions (doing things)

Functions are defined with [`func`](../compiler/lexer.py:33). We keep the syntax clean—no semicolons at the end of every line, and the last expression evaluated is automatically returned.

```text
func calculate_speed(distance, time) {
    distance / time // No 'return' keyword needed!
}
```

The `main` function is the entry point of your program. In the 1.2.2 prototype it has a fixed no-argument entry shape; declaring parameters on `main` is a compile-time error. When you run your executable, this is where the action starts.

```text
func main() {
    let speed = calculate_speed(120, 2)
    print(speed)
}
```

Defining a function does not call it. The entry point calls the calculation
function using its name and arguments. For the smallest complete program, see
the [Hello World example](../examples/01_hello.kn).

## 3. Control Flow (making decisions)

Our `if` and `else` statements look exactly how you'd expect, minus the clutter of unnecessary parentheses around the condition.

```text
let speed_limit = 70
let speed = 85

if speed > speed_limit {
    print("Uh oh, speeding ticket!")
} else {
    print("Safe driving!")
}
```

Comparisons in 1.2.2 are limited to equality, less-than, and greater-than. They
work on integers and, bytewise, on strings.

## 4. Loops (doing things repeatedly)

Need to do something over and over? The `while` loop has your back. Just remember to use a mutable variable so you don't loop forever!

```text
mut i = 0

while i < 3 {
    print("Looping...")
    i = i + 1
}
```

## 5. Arrays (lists of things)

Version 1.2.2 arrays contain integers. Array literals and indexed reads are supported;
arrays of strings and mixed element types are not part of the current language.

```text
let high_scores = [100, 95, 80]

// Arrays are zero-indexed, meaning the first item is at position 0.
let top_score = high_scores[0] 
print(top_score)
```

The analyzer preserves a known array length through direct binding copies and
reassignment when the source length is known. Across conditionals and loops it
keeps that fact only when every possible path agrees, so a stale length is not
used for a later constant bounds diagnostic.

Behind the scenes, the LLVM backend uses pointer arithmetic to access array elements. This is a prototype implementation, not a guarantee of memory safety or zero runtime cost.

### Array and string length

[`len()`](../compiler/analyzer.py:450) is a compiler builtin accepting exactly one
integer array or string. For an array it returns the element count; an empty
array has length zero. For a string it returns the number of bytes before the
terminator, matching C's `strlen`. Integers, booleans, missing arguments, and
multiple arguments are rejected. The name is reserved for the builtin when
declaring functions.

```text
func main() {
    mut values = [10, 20, 30]
    print(len(values))
    values = [40]
    print(len(values))
    let empty = []
    print(len(empty))
}
```

The length is not inferred from a stale declaration: it is part of the array's
runtime value. Array copies and function arguments/results carry both the data
pointer and count. Reassignment changes both fields for the destination binding.
The builtin evaluates its argument once and does not traverse the elements.
See [array lengths](../examples/08_array_lengths.kn) for a complete example.

### Runtime bounds checks

Every indexed read checks that its index is nonnegative and strictly less than
the current array length. String byte reads apply the same rule against the
string's byte length, and `slice` validates its start and end against the same
bounds. Negative indexes do not count backward. Indexing an
empty array always fails. Known constant out-of-bounds reads remain compile-time
errors; dynamic invalid reads trap at runtime before the element address is
computed or read. A trap terminates the process with a platform-dependent failure
status, not a recoverable language exception or a formatted diagnostic message.
The CLI's run command propagates failure; it no longer reports success for a
failed child process.

These checks apply to literal arrays, aliases, mutable bindings, and array
parameters, including after control-flow merges. They protect the index range,
not the validity of an already dangling pointer.

### Array storage and allocation failure

Since 1.2.1, array literals allocate element storage from the C heap at the point
of construction, and that storage lives until the process exits. Returning a
locally created array from a helper is therefore well-defined: the data pointer
and count in the returned aggregate stay valid for the rest of the program.
The prototype never reuses or frees this storage, so repeated construction leaks
memory by design. This is a deliberate simplification, not a production
memory-safety model.

The [array-lifetime example](../examples/09_array_lifetimes.kn) demonstrates
returned local arrays remaining valid after another helper allocates an array.

If allocation for a nonempty array returns a null pointer, the executable traps
before evaluating or storing any elements. Like a bounds trap, this terminates
the process rather than returning a recoverable status or a formatted diagnostic.
An empty array may have a null data pointer without an allocation trap; its length
remains zero and every indexed read is rejected by the bounds check.

There is still no resizing, indexed assignment, or general ownership model.
The pointer/count representation introduced in 1.2.0 is unchanged in 1.2.1.
Regenerate IR and native binaries to pick up the lifetime and allocation fixes.

---

## 6. Strings (working with text)

Strings are immutable byte sequences. Literals embed in the compiled binary;
operations that build new text allocate NUL-terminated storage at runtime
through the C library.

```text
let name = "Kinetic"
print(len(name))          // 7 bytes
print(name[0])            // 75, the ASCII byte for 'K'
print(slice(name, 0, 3))  // "Kin"
print("Hello, " + name + "!")
```

- Indexing a string reads one byte as an integer. The same runtime guard as
  array indexing applies: a negative or out-of-range index traps before the
  byte is read.
- `==`, `<`, and `>` compare strings bytewise, like C's `strcmp`. Mixing a
  string with an integer operand is a compile-time error, and `-`, `*`, `/`
  are not defined for strings.
- `+` concatenates two strings into newly allocated storage.
- `slice(text, start, end)` copies the bytes from `start` up to but not
  including `end` into a new string. The name is reserved for the builtin when
  declaring functions. A negative start, an end before the start, or an end
  past the string's byte length traps at runtime.

Literals cannot contain NUL bytes, escaped or raw; the lexer rejects them
because runtime storage is NUL-terminated. The function names `printf`,
`malloc`, `strlen`, `strcmp`, and `memcpy` are reserved for the C runtime
symbols the backend emits, alongside the builtin names `len` and `slice`.

Type inference defaults are unchanged: a parameter used only through `len`,
indexing, or a binary operator, and never constrained by a call site, still
infers as an integer array or integer. Passing a string at a call site
constrains the parameter to a string before those defaults apply.

See the [text example](../examples/10_text.kn) for a complete program.

## 7. Status handling and byte processing

The [status example](../examples/06_status_handling.kn) returns an integer from a
local validation function and branches on success or failure. Zero means success
by convention; nonzero means failure. This is ordinary program logic, not a new
status type, exception facility, or compiler diagnostic.

The [byte example](../examples/07_byte_processing.kn) counts ASCII digits stored
in an integer array. It queries the actual array length and bounds its loop using
that count; reads also carry runtime checks. Dynamic byte buffers and Unicode
decoding remain unavailable. Integer arrays are not restricted to byte values.

Both illustrate the [bootstrap interface design](bootstrap_interface.md) without
implementing its native services. See the [example catalog](../examples/README.md)
for expected outputs and separate error/warning demonstrations.
