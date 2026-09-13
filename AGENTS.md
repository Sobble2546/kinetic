# Agent guidance

Kinetic is a 1.2.1 prototype language compiler written in Python. It emits textual
LLVM IR through llvmlite and invokes Clang for native binaries. Keep changes small
and do not imply that the prototype provides a production memory-safety model.

## Layout

- [Compiler sources](compiler/README.md) form one flat Python package, with stage files directly in the compiler directory.
- [Root launcher](kinetic.py) delegates to the compiler CLI.
- [Package configuration](pyproject.toml) installs the compiler package directly.
- [Tools](tools/README.md), [tests](tests/README.md), [docs](docs/README.md), and
  [examples](examples/README.md) have separate responsibilities.

Use package-relative imports within the compiler. Keep the launcher thin and
avoid additional package layers or duplicate implementations. Sample programs
belong in the examples directory.

## Setup and commands

Install the sole runtime dependency from [requirements.txt](requirements.txt):

```shell
python -m pip install -r requirements.txt
```

An editable installation is optional:

```shell
python -m pip install -e .
```

Clang must be on the executable search path for native builds:

```shell
python kinetic.py build examples/01_hello.kn
python kinetic.py run examples/01_hello.kn
```

## Verification

For structural changes, run the static-only checker:

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

It needs only Python and does not import Kinetic, generate IR, invoke Clang, or
run Kinetic programs. See [tests](tests/README.md) for its coverage.

The general [runner](tools/check.py) is not static-only: it discovers frontend,
backend, and opt-in native suites as well as layout checks. Backend tests generate
IR when llvmlite is installed. Use the explicit layout command for static-only work.

The [workflow](.github/workflows/ci.yml) runs the general runner in its
Windows/Linux Python 3.10/3.14 matrix without installing llvmlite. A separate
Ubuntu job installs the runtime dependency and runs frontend/backend tests. A
third Ubuntu job enables native testing and builds and runs the native example
suite with the runner-provided Clang toolchain. Keep test logic shared between
local and hosted runs; a green layout check alone does not demonstrate compiler
behavior.

Automated behavioral suites exist; there is no configured linter. When compiler
behavior changes and native builds are permitted, verify the numbered examples:

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
```

**If the user asks not to compile or run programs, do not invoke these commands,
the compilation API, or native tools. Limit verification to static checks and
report that behavioral verification was skipped.**

Native build and run operations write IR and binaries next to the source.
[.gitignore](.gitignore) covers common outputs and Python/package caches, but
remove artifacts after manual verification. A Clang warning about overriding the
module target triple is benign on its own.

## Architecture

The root launcher delegates to the [CLI](compiler/cli.py), which calls
[`compile_with_diagnostics()`](compiler/compiler.py:7), the single pipeline
orchestration point. [`compile_source()`](compiler/compiler.py:23) wraps it for
callers that need only the IR.

The stage order is [lexer](compiler/lexer.py),
[parser](compiler/parser.py), [analyzer](compiler/analyzer.py), and
[LLVM backend](compiler/backend.py). The orchestration API verifies the
IR with llvmlite before returning it.

Printing is a compiler builtin, not a user-level or library function. It is
special-cased in both the analyzer and backend, lowers to C's formatted-output
function, and accepts exactly one integer or string. New builtins need matching
handling in both stages.

The array-length builtin accepts exactly one integer array. Arrays lower to
pointer/count aggregates, including in function signatures and mutable storage.
Every indexed read has a runtime range guard before element address calculation
and loading; failure traps. Preserve both fields through copying/reassignment
and do not equate bounds checking with lifetime safety. Array element storage
is heap-allocated at construction and lives until process exit; it is never
freed or reused, so returning locally created arrays is well-defined but repeated
construction leaks — do not describe this as reclamation or a memory-safety model.
A failed nonempty-array allocation traps before element initialization. Empty
arrays may have null data pointers; their length is zero and every read fails
the bounds check. The CLI propagates failed child exit statuses. Test
[runtime failures](examples/runtime_errors/README.md)
separately from success examples when native execution is permitted.

The [syntax guide](docs/syntax_guide.md) documents the 1.2.1 language. The nine
numbered [examples](examples/README.md) cover inference, control flow, mutation,
and array lengths/lifetimes. Comparisons remain limited to equality, less-than,
and greater-than.

Declarations use [`func`](compiler/lexer.py:33) for functions,
[`let`](compiler/lexer.py:34) for immutable bindings, and standalone
[`mut`](compiler/lexer.py:35) for mutable bindings. Keep lexer tokens, parser
handling, examples, and documentation synchronized when syntax changes.

See [architecture](docs/architecture.md) and [contributing](CONTRIBUTING.md) before
changing compiler boundaries or verification workflows.

## Direction and status

The [roadmap](ROADMAP.md) tracks completed work, current planning, and future
milestones toward self-hosting. Kinetic is not self-hosting yet; the compiler is
implemented in Python. Do not describe planned language or runtime features as
available, and update milestone status only when the work and its verification
are actually complete.

[Claude Code guidance](CLAUDE.md) imports these shared instructions.
[Fallback guidance](AGENT.md) points tools using the singular filename here.
Keep this document authoritative rather than maintaining divergent rule sets.

The [bootstrap host interface](docs/bootstrap_interface.md) is a design contract.
The status/byte examples illustrate concepts using existing syntax; do not
describe them as native-service implementations. Keep explanatory comments and
docstrings out of Python files, and preserve historical versions in migration hints.
