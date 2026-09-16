# Development tools

Repository maintenance utilities live here, separate from the
[compiler CLI](../compiler/cli.py).

## Static-only verification

From the repository root:

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

This selects only the [layout suite](../tests/test_layout.py). It checks Python
syntax, repository structure, import targets, and documentation links without
importing Kinetic, generating LLVM IR, invoking Clang, or running Kinetic programs.
It needs only Python and leaves no bytecode caches.

## General test runner

From the repository root:

```shell
python -B tools/check.py
```

The [runner](check.py) discovers layout, frontend, backend, and native suites.
It returns a nonzero status on failure and does not install dependencies.

- Frontend tests import and exercise the lexer, parser, and analyzer.
- Backend tests generate and verify IR when llvmlite is installed; they are
  skipped when the dependency is unavailable.
- Native tests require explicit opt-in plus Clang and llvmlite. They build and
  execute programs in temporary directories.

The 1.3.0 suites include array-length inference, descriptor propagation,
indexed writes, emitted
bounds guards, heap-backed element storage, and returned arrays surviving later
calls, as well as unsuccessful native exits for invalid indexes. The
[runtime-failure examples](../examples/runtime_errors/README.md) are tested
separately from successful numbered examples. They must not be run during
static-only work.

**The general runner is not static-only.** Do not invoke it when compiler
execution or IR generation is prohibited. Although it locates tests relative to
itself, some behavioral tests read examples relative to the working directory;
run it from the repository root.

See [tests](../tests/README.md) for individual suite commands and native opt-in.

## GitHub Actions

The [workflow](../.github/workflows/ci.yml) invokes the general runner on Windows
and Linux using Python 3.10 and 3.14 without installing llvmlite. Despite its
static label, this matrix includes frontend behavior tests. A separate Ubuntu
Python 3.10 job installs the runtime dependency and runs frontend/backend suites.
A third Ubuntu job enables native testing and uses the runner-provided Clang
toolchain to build and execute the numbered examples and runtime-failure
programs. Test logic is shared with local runs.
