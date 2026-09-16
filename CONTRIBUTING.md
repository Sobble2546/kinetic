# Contributing to Kinetic

Kinetic is a small prototype. Prefer focused changes and explicit compiler
stages over adding infrastructure intended for a much larger language project.

## Start here

- [Installation](INSTALL.md) covers the source-checkout and editable-install workflows.
- [Architecture](docs/architecture.md) explains the compilation pipeline.
- [Repository layout](docs/repository_layout.md) explains where changes belong.
- [Language guide](docs/syntax_guide.md) documents the existing 1.3.0 surface.
- [Bootstrap host interface](docs/bootstrap_interface.md) defines a future interface, not available builtins.
- [Roadmap](ROADMAP.md) tracks implemented features and the path toward self-hosting.

## Where to make changes

| Change | Location |
| --- | --- |
| Tokenization and grammar | [Lexer](compiler/lexer.py), [tokens](compiler/tokens.py), and [parser](compiler/parser.py). |
| Syntax representation | [AST](compiler/ast.py). |
| Type rules and inference | [Analyzer](compiler/analyzer.py) and [types](compiler/types.py). |
| LLVM generation | [Backend](compiler/backend.py). |
| Pipeline orchestration | [Compiler API](compiler/compiler.py). |
| User-facing build and run commands | [CLI](compiler/cli.py). |
| Maintenance commands | [Tools](tools/README.md). |
| Validation | [Tests](tests/README.md) and [examples](examples/README.md). |

Keep compiler stages directly in the compiler package, using package-relative
imports. The root [launcher](kinetic.py) should delegate to the CLI rather than
contain another implementation of the build workflow.

Printing is currently a compiler builtin, not a library function. Changes to
builtins need matching analyzer and backend handling. Do not create a placeholder
standard-library tree before there is an actual library implementation.

The array-length builtin likewise requires matching analyzer and backend
handling. Preserve pointer/count metadata across array copies, mutable storage,
function calls, and value-producing branches. Runtime read checks must dominate
element pointer arithmetic and loads. Cover empty arrays, negative and upper
bounds, changing lengths, and failure exit statuses in regression tests. Bounds
checks do not replace a lifetime model or justify a general memory-safety claim.

Array elements use heap storage that remains allocated until process exit, so
returning local arrays is supported but repeated construction leaks. Preserve
the trap before initialization when a nonempty-array allocation fails, and keep
empty arrays valid even if their zero-size allocation returns a null pointer.

## Static verification

Run the static checker before submitting a layout or documentation change:

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

This suite uses only the Python standard library. It verifies Python
syntax, internal import targets, the single compiler source location, public API
exports, entry points, declaration-token references, the published Hello World
example, and local documentation links.

It does not import the compiler or generate IR. For frontend behavior only:

```shell
python -B -m unittest discover -s tests -p test_frontend.py -v
```

The general [runner](tools/check.py) discovers all test suites, including backend
tests that generate IR when llvmlite is installed. It is not static-only.
Native tests additionally require explicit opt-in and a working toolchain;
see [tests](tests/README.md) for Windows and Unix-like commands.

## GitHub CI

The [workflow](.github/workflows/ci.yml) runs the full local checker on pushes,
pull requests, and manual dispatches (Windows and Linux, Python 3.10 and 3.14).
A second `behavioral` job installs the constrained llvmlite dependency from
[requirements.txt](requirements.txt) and runs the frontend and backend suites on
Ubuntu with Python 3.10. A third `native` job enables native testing and uses
the runner-provided Clang toolchain to build and execute every numbered example
and the runtime-failure programs on Ubuntu.

CI uses read-only repository permissions and official actions pinned to commit
hashes. The matrix job does not install llvmlite, but still executes frontend
tests despite its static label. The behavioral job installs the dependency
constrained in [requirements.txt](requirements.txt). The native job sets
`KINETIC_NATIVE_TESTS=1`; keep it as a separate, clearly named job and keep the
layout suite usable without a compiler toolchain. Keep test logic in the suites
rather than duplicating it in CI.

Run checks locally for fast feedback; CI makes them repeatable for every change.
A green static job does not replace compiler-behavior verification, but the
results of a passing hosted native job provide end-to-end evidence for the
covered cases at that revision. Merely configuring a job does not prove it passed.

## Compiler verification, when builds are appropriate

Changes to compiler behavior should also be checked against the numbered examples
in an environment with llvmlite and Clang installed:

```shell
python kinetic.py run examples/01_hello.kn
python kinetic.py run examples/02_logic.kn
python kinetic.py run examples/03_arrays.kn
python kinetic.py run examples/04_bounds_checked.kn
python kinetic.py run examples/05_mutability.kn
python kinetic.py run examples/06_status_handling.kn
python kinetic.py run examples/07_byte_processing.kn
python kinetic.py run examples/08_array_lengths.kn
python kinetic.py run examples/09_array_lifetimes.kn
python kinetic.py run examples/10_text.kn
python kinetic.py run examples/11_indexed_writes.kn
```

These commands **do compile and execute programs**. Do not use them when a task
requests static-only work. Remove generated artifacts afterward. The automated
frontend, backend, and opt-in native suites are described in [tests](tests/README.md).
Do not mix the intentional error examples into success-only build loops.
The [runtime-failure examples](examples/runtime_errors/README.md) intentionally
terminate unsuccessfully after compiling; verify them separately with nonzero
exit expectations when native execution is allowed.

## Before submitting

- Keep changes scoped to the task; do not mix a file move with language changes.
- Keep the launcher, package exports, and installed command aligned.
- Update documentation links and package configuration when moving files.
- Add examples or regression coverage for language changes.
- Update the roadmap when a milestone's actual status changes; planned work is not implemented work.
- Report which checks actually ran, and which were deliberately skipped.
- Keep current-version descriptions aligned with [package metadata](pyproject.toml),
  while preserving historical syntax-removal versions. Keep Python sources free
  of explanatory comments and docstrings; explanations belong in these guides.
