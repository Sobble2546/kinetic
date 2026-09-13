# Kinetic

A small language compiler, written in Python and targeting LLVM.

[Language guide](docs/syntax_guide.md) · [Architecture](docs/architecture.md) · [Installation](INSTALL.md) · [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md)

Kinetic is an early compiler prototype (1.2.2). It reads Kinetic source, performs
lexical, syntactic, and type analysis, emits verified textual LLVM IR through
llvmlite, and uses Clang to produce a native executable.

The long-term goal is a readable systems language. The current prototype is
deliberately small; it does not yet provide a standard library or a production
memory-safety model.

## Language features

- Type inference and implicit function returns.
- Immutable bindings with opt-in mutation.
- Conditional branches and loops.
- Integer and string values, integer arrays, and array indexing.
- Array element counts through the length builtin and runtime checks on indexed reads.
- String length, byte reads, bytewise comparisons, slicing, and concatenation.
- A built-in printing operation for one integer or string at a time.

Start with the [language guide](docs/syntax_guide.md) and the programs in
[examples](examples/README.md).

## Hello World

The [introductory example](examples/01_hello.kn) is a complete Kinetic program:

```text
func main() {
    print("Hello World!")
}
```

Functions use [`func`](compiler/lexer.py:33), immutable bindings use
[`let`](compiler/lexer.py:34), and mutable bindings use
[`mut`](compiler/lexer.py:35). See the [syntax guide](docs/syntax_guide.md) for
declarations, reassignment, and function calls.

## Quick start

You need Python 3.10 or newer, a compatible llvmlite release, and Clang on your
executable search path. See [installation](INSTALL.md) for details.

Install the Python dependency:

```shell
python -m pip install -r requirements.txt
```

Compile and run the introductory example:

```shell
python kinetic.py run examples/01_hello.kn
```

Compile without running the result:

```shell
python kinetic.py build examples/01_hello.kn
```

The root [launcher](kinetic.py) provides the build and run commands. Generated IR
and native binaries are written next to the input source.

## Repository layout

Compiler sources, documentation, examples, and development utilities each have
one clear location.

| Area | Responsibility |
| --- | --- |
| [Compiler](compiler/README.md) | A flat Python package containing all compiler stages and the CLI. |
| [Documentation](docs/README.md) | Language reference, architecture, and repository design. |
| [Examples](examples/README.md) | Ten numbered programs plus compile-time error, runtime-failure, and warning examples for 1.2.2. |
| [Tools](tools/README.md) | Repository maintenance utilities, separate from the compiler CLI. |
| [Tests](tests/README.md) | Separate layout, frontend, backend, and opt-in native suites. |
| [Package configuration](pyproject.toml) | Python packaging and the optional installed command. |

See the [layout guide](docs/repository_layout.md) for the directory responsibilities.

## Development

Run the dependency-free, static-only repository checks:

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

This checks syntax, layout, links, and keyword mapping without importing the
compiler or generating IR. The general [test runner](tools/check.py) also
discovers behavioral tests: frontend tests run directly, backend tests generate
IR when llvmlite is installed, and native tests require explicit opt-in plus
Clang and llvmlite. Do not use that general runner for static-only work.

The [GitHub Actions workflow](.github/workflows/ci.yml) runs on pushes, pull
requests, and manual dispatches. Its Windows/Linux matrix runs the general
runner on Python 3.10 and 3.14 without installing llvmlite. A separate Ubuntu
Python 3.10 job installs the runtime dependency and runs frontend/backend tests.
A third Ubuntu job enables native testing and uses the runner-provided Clang
toolchain to build and execute all ten numbered examples plus the
runtime-failure programs. A passing native job verifies the covered end-to-end
behavior for that revision; configuration alone is not evidence of success. See
[contributing](CONTRIBUTING.md).

### New in 1.2.2

Strings gain source-text operations. `len()` reports a string's byte length,
indexing reads one byte with the same runtime range guard as arrays, `==`/`<`/`>`
compare bytewise, `+` concatenates into new storage, and the reserved `slice()`
builtin copies a checked start/end range into new NUL-terminated storage. The
[text example](examples/10_text.kn) demonstrates each operation. String result
storage is allocated at runtime and never reclaimed, matching the prototype's
array-storage simplification rather than a memory-safety model.

### Fixed in 1.2.1

Array element storage now lives on the heap until process exit, so helpers can
return locally created arrays without leaving their callers with stack-backed
data. A failed allocation for a nonempty array traps before any elements are
initialized. Empty arrays remain valid length-zero values.

This is a patch release for existing array behavior; source syntax is unchanged.
Storage is never reclaimed, so repeated construction leaks memory. These fixes
do not introduce garbage collection, ownership checking, or a production
memory-safety model. The [array-lifetime example](examples/09_array_lifetimes.kn)
demonstrates returned data surviving later calls. See
[array semantics](docs/syntax_guide.md) for details.

### New in 1.2.0

The [array-length example](examples/08_array_lengths.kn) demonstrates
[`len()`](docs/syntax_guide.md:117): an integer-array element count that travels
with the array through copies, reassignment, and function calls. The
[byte-processing example](examples/07_byte_processing.kn) now uses this builtin
instead of a manually synchronized length.

Every indexed read emits a negative/upper-bound check before computing the
element address and loading it. A failed runtime check traps, and run mode
returns failure. [Runtime-failure examples](examples/runtime_errors/README.md)
are separate from compile-time diagnostic examples. These checks do not detect
dangling array storage, make arrays resizable, or provide production memory safety.

This is an implementation change, not only a design update. Frontend, IR, native,
and CLI regression tests cover it, and the hosted native CI job builds and runs
the native suites on every push. The
[bootstrap interface](docs/bootstrap_interface.md) itself remains a specification.

## Direction

The current goal is to build the foundations needed for a compiler written in
Kinetic that can compile itself. Version 1.2.2 is not self-hosting yet. The
[roadmap](ROADMAP.md) separates completed work, current planning, and future milestones.

## License

See [LICENSE](LICENSE).
