# Installing and running Kinetic

These instructions describe Kinetic 1.3.0. The version is declared in
[package configuration](pyproject.toml).

## Requirements

- Python 3.10 or newer, with a version supported by the llvmlite release you install.
  A stable Python release is recommended; prerelease interpreters may not have
  compatible llvmlite wheels.
- llvmlite, the only runtime Python dependency, constrained to the 0.45 release
  series in [requirements.txt](requirements.txt). This is not an exact patch pin.
- Clang on your executable search path for native builds and execution.

Clang is a separate toolchain dependency; installing the Python requirements
does not install it. Static repository checks need only Python.

## Work directly from a checkout

From the repository root, install the dependency listed in
[requirements.txt](requirements.txt):

```shell
python -m pip install -r requirements.txt
```

The root [launcher](kinetic.py) works without installing Kinetic itself:

```shell
python kinetic.py build examples/01_hello.kn
python kinetic.py run examples/01_hello.kn
```

The module entry point is also available:

```shell
python -m compiler run examples/01_hello.kn
```

## Optional editable installation

The [package configuration](pyproject.toml) installs the single
[compiler package](compiler/README.md):

```shell
python -m pip install -e .
```

This also installs the command-line entry point:

```shell
kinetic run examples/01_hello.kn
```

The editable installation reads its runtime dependency from the same
[requirements.txt](requirements.txt), so the two installation paths share one
dependency list. Paths to input programs are relative to your current working
directory.

## Build output

Both build and run write textual LLVM IR and a native executable next to the
input source. Windows executables have the usual executable extension;
Unix-like executables have no extension. The run command builds first and then
starts the resulting executable.

Clang may print a warning about overriding the module target triple. On its own,
that warning is not a build failure.

Common generated outputs are covered by [.gitignore](.gitignore). Remove artifacts
after manual verification, especially binaries from newly added examples.

The [example catalog](examples/README.md) includes eleven valid numbered programs,
compile-time failures, runtime bounds failures, and warning demonstrations. The bootstrap status and byte
examples use the existing language; the proposed host services are not installed
by these setup commands.

Regenerate existing IR and binaries when upgrading to 1.2.1 to pick up the
heap-backed array-lifetime and allocation-failure fixes. The pointer/count
representation introduced in 1.2.0 is unchanged. Array storage now lives until
process exit and is not reclaimed; failed nonempty-array allocations trap before
initialization. These fixes use the existing C runtime and add no dependency to
the installation steps.

An invalid runtime index or failed nonempty-array allocation traps and returns
failure from the run command; the exact native exit status or signal is
platform-dependent. The runtime-failure examples demonstrate bounds failures
and must not be included in a success-only build-and-run loop.

## Static checks without a compiler toolchain

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

This does not require llvmlite or Clang and does not compile or run Kinetic code.
See [tests](tests/README.md) for the scope of these checks and the separate
behavioral commands. The general [runner](tools/check.py) is not static-only:
it discovers backend tests that generate IR when llvmlite is installed.
