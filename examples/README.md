# Kinetic examples

These are complete programs for learning and experimenting with the 1.2.1 language.

| Program | Focus |
| --- | --- |
| [Hello World](01_hello.kn) | A minimal function that prints a greeting. |
| [Logic](02_logic.kn) | Immutable and mutable bindings, conditional branches, and loops. |
| [Arrays](03_arrays.kn) | Array indexing, arithmetic, and a conditional check. |
| [Bounds-checked arrays](04_bounds_checked.kn) | Valid constant indexes with compile-time diagnostics and runtime read guards. |
| [Mutability](05_mutability.kn) | `let` versus `mut` declarations and legal reassignment. |
| [Status-code handling](06_status_handling.kn) | Validate a byte and handle the returned success or failure status. |
| [Byte processing](07_byte_processing.kn) | Count ASCII digits using the array-length builtin. |
| [Array lengths](08_array_lengths.kn) | Lengths of empty arrays, copies, reassigned bindings, and function arguments/results. |
| [Array lifetimes](09_array_lifetimes.kn) | Read a locally created array after its helper returns and another helper allocates an array. |
| [Text operations](10_text.kn) | String length, byte reads, comparisons, slicing, and concatenation. |

Read the [syntax guide](../docs/syntax_guide.md) for the language rules.

Declarations use [`func`](../compiler/lexer.py:33) for functions,
[`let`](../compiler/lexer.py:34) for immutable bindings, and standalone
[`mut`](../compiler/lexer.py:35) for mutable bindings.

## Bootstrap interface concepts

The [status-handling example](06_status_handling.kn) and
[byte-processing example](07_byte_processing.kn) use existing language features
to illustrate concepts from the [bootstrap host interface](../docs/bootstrap_interface.md).
They do not call native host services or implement opaque buffers, file I/O,
or toolchain invocation. The byte example does use the implemented length
builtin and runtime array-read checks.

Expected output for the status-handling example:

```text
Byte accepted
Invalid byte
```

Expected output for the byte-processing example:

```text
ASCII digits:
3
```

Expected output for the [array-length example](08_array_lengths.kn):

```text
Array lengths:
3
2
3
0
2
```

Expected output for the [text example](10_text.kn):

```text
Text operations:
7
75
Kin
Hello, Kinetic!
equal
ordered
```

These are program output expectations, excluding the launcher's build/run
messages. The hosted native CI job builds and runs every numbered example with
Clang on each push and checks for the expected output fragments; locally the native suite remains
opt-in via `KINETIC_NATIVE_TESTS=1`.

## Returned array lifetimes

The [array-lifetime example](09_array_lifetimes.kn) returns a locally created
array, calls another helper that allocates scratch storage, then prints the
original elements and length. The original data remains valid because array
element storage lives until process exit; it is not reclaimed.

Expected output:

```text
Scratch array:
40
Returned array:
7
8
9
Returned length:
3
```

## Diagnostic examples

The compiler emits structured diagnostics at compile time:

- **[errors/](errors/README.md)** — programs that fail to compile, each
  demonstrating one `kinetic: error: line:column` diagnostic (immutable
  reassignment, out-of-bounds indexes, missing or invalid `main`, duplicate
  parameters, removed syntax, undefined variables, type mismatches).
- **[warnings/](warnings/README.md)** — programs that compile and run but emit
  `kinetic: warn` diagnostics (unused bindings, shadowing).
- **[runtime_errors/](runtime_errors/README.md)** — programs that pass analysis
  but terminate at a runtime bounds check. Keep these out of success-only runs.

Array copies share element storage, but rebinding a mutable array updates that
binding's pointer and length together without changing an earlier copy's length.
Element storage is heap-allocated at construction and lives until the process
exits, so returning a locally created array is well-defined; the prototype never
reclaims this storage and leaks it by design. Bounds checks protect the index
range, not reclamation or a general memory-safety model. A failed allocation for
a nonempty array traps before initialization. The runtime-failure examples above
exercise invalid reads, not allocation failure.

## Running an example

When native builds are appropriate and the toolchain is installed, run an example
from the repository root:

```shell
python kinetic.py run examples/01_hello.kn
```

This command compiles and executes the program and writes artifacts alongside
the source. It is not part of the [static repository checks](../tests/README.md).
