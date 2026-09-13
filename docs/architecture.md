# Compiler architecture

Kinetic's 1.2.2 implementation lives in the [compiler source directory](../compiler/README.md).
It is a flat Python package with separate modules for each compilation stage.

## Entry points

The root [launcher](../kinetic.py) delegates to the
[CLI](../compiler/cli.py). The CLI reads a source file, calls the
[compilation API](../compiler/compiler.py), writes the resulting IR,
and invokes Clang to link a native executable. Run mode then starts it.

The [module launcher](../compiler/__main__.py) and the installed command
declared in [pyproject.toml](../pyproject.toml) delegate to the same CLI; there are
no separate implementations for these entry points.

## Pipeline

| Step | Input → output | Implementation |
| --- | --- | --- |
| Lexing | Source text → tokens with locations | [Lexer](../compiler/lexer.py) and [tokens](../compiler/tokens.py) |
| Parsing | Tokens → abstract syntax tree | [Parser](../compiler/parser.py) and [AST](../compiler/ast.py) |
| Semantic analysis | Syntax tree → inferred and checked types | [Analyzer](../compiler/analyzer.py) and [types](../compiler/types.py) |
| Code generation | Checked program → textual LLVM IR | [LLVM backend](../compiler/backend.py) |
| IR verification | Textual IR → verified textual IR | [Pipeline coordinator](../compiler/compiler.py) using llvmlite's LLVM bindings |
| Native build | Verified IR → native executable | [CLI](../compiler/cli.py) invoking Clang |

The pipeline is coordinated by
[`compile_with_diagnostics()`](../compiler/compiler.py:7), which returns verified
IR and a diagnostics collector. [`compile_source()`](../compiler/compiler.py:23)
wraps it for callers that only need IR. Errors raise subclasses of
[`KineticError`](../compiler/errors.py:1). The CLI displays line/column information
where the error provides it; not every error currently has a location. Warnings
are collected during analysis and displayed with a singular/plural summary.
Errors stop the pipeline at the first failure; this is not multi-error recovery.

The analyzer emits warnings for unused bindings and shadowing, and reports
errors for immutable reassignment, undefined names, type mismatches, constant
out-of-bounds array indexes, an invalid `main` entry point, and duplicate
function parameters. Lexical binding identity is preserved while analyzing
shadowing so usage diagnostics and scoped array facts refer to the declaration
that is actually visible. The lexer
rejects removed syntax (such as `fn`) with an explicit migration hint, and the
parser rejects `let mut` with guidance toward standalone `mut`.

## Shared representations and diagnostics

The lexer and parser share token definitions; the parser, analyzer, and backend
share the syntax tree. The analyzer and backend share type definitions. User-facing
errors derive from the base exception in [errors](../compiler/errors.py).

The printing builtin is special-cased by both the analyzer and the backend and
lowers to C's formatted-output function. It accepts exactly one integer or string.
It is not evidence of a separate runtime or standard library.

The length builtin is also handled by both stages. Analysis requires one
integer array or string, supports parameter inference, rejects redefinition as
a user function, and returns an integer type. For arrays the backend extracts
the count from the aggregate after evaluating the argument once; for strings it
calls C's `strlen`. The `slice` builtin is reserved alongside it: analysis
requires a string with integer start and end indexes and returns a string.

## Array representation and read checks

The backend lowers integer arrays to an LLVM aggregate containing a data pointer
and a 64-bit element count. Literals construct both fields, mutable bindings
store/load the aggregate, and function signatures and value-producing branches
carry the same aggregate. Reassignment therefore updates pointer and length
together, and aliases keep their original metadata.

Before each element read, the backend compares the signed index against zero
and the array length. It branches to an element-address/load block only when
both tests pass. The failure block calls the LLVM trap intrinsic and terminates
with an unreachable instruction. No invalid element pointer is computed on that
path. LLVM may later simplify redundant constant checks; the compiler emits them
for every source-level read.

Array literals allocate element storage with the C allocator; the returned
pointer is stored in the aggregate alongside the element count. Allocation
happens at each construction site, including inside loops, and the storage is
never freed or reused, so repeated construction leaks memory. Since 1.2.1,
returning a locally created array is well-defined because its element storage
outlives the constructing frame.

For a nonempty array, the backend checks the allocation result before evaluating
or storing any elements. A null pointer branches to a trap and unreachable
terminator; initialization proceeds only on the success branch. An empty array
requests zero bytes and may receive a null pointer without trapping. Its count
is zero, so the bounds guard rejects every indexed read without dereferencing
that pointer.

Runtime range checks protect only the index range; neither they nor the
allocation-failure guard reclaim storage, prevent unbounded growth, or
constitute a production memory-safety model. The pointer/count representation
was introduced as an internal ABI change in 1.2.0 and is unchanged in 1.2.1;
it is not the proposed host adapter's opaque-buffer ABI.

The CLI preserves nonnegative child exit statuses and maps signal termination
to failure, so a bounds or allocation trap does not appear as a successful run command.

## String representation and operations

Strings lower to NUL-terminated byte pointers. Literals are private constants;
indexing reads one byte after the same range guard used for arrays, with the
loaded byte zero-extended to an integer. `==`, `<`, and `>` lower to C's
`strcmp` result compared against zero. `+` and `slice` allocate result storage
with C's `malloc`, copy bytes with `memcpy`, and write the terminating NUL
byte. The compiler does not track allocation lifetimes for these results.

## Package organization

The [package initializer](../compiler/__init__.py) exposes the compilation API.
Stage modules use package-relative imports, and the root launcher imports the
CLI from this package. An editable installation is optional when working from
the repository root; the installed command uses the same code.

## Boundaries

- Compiler implementation and the user-facing CLI belong in the compiler package.
- Repository maintenance belongs in [tools](../tools/README.md).
- Static regression checks belong in [tests](../tests/README.md).
- Tutorials and complete sample programs belong in [examples](../examples/README.md).
- User and contributor explanations belong in [documentation](README.md).

The [roadmap](../ROADMAP.md) tracks the language, runtime, and validation work
needed before Kinetic can host its own compiler. Those planned components are
not part of the 1.2.2 implementation described here.

The [bootstrap host interface](bootstrap_interface.md) specifies the future
native-service boundary, buffer ownership, and textual-IR build protocol. It is
a design contract, not an implemented extension to the current compiler.

The [status](../examples/06_status_handling.kn),
[byte-processing](../examples/07_byte_processing.kn), and
[array-length](../examples/08_array_lengths.kn) demonstrations use the current
compiler. The byte and length examples exercise the new builtin and array
metadata; none implements the host adapter, buffer handles, or native I/O.

Verification is split into [layout, frontend, backend, and native suites](../tests/README.md).
Only the explicit layout suite is static-only; the general runner can generate
IR when llvmlite is available.
