# Repository layout

Kinetic keeps its implementation flat and separates it from documentation,
examples, and repository maintenance.

## Directories

| Directory | Responsibility |
| --- | --- |
| [Compiler](../compiler/README.md) | The Python package, with the lexer, parser, analyzer, backend, and CLI directly inside it. |
| [Documentation](README.md) | Language syntax, compiler architecture, and repository guides. |
| [Examples](../examples/README.md) | Complete Kinetic programs used in tutorials and manual verification. |
| [Tools](../tools/README.md) | Development and repository maintenance utilities. |
| [Tests](../tests/README.md) | Layout, frontend, backend, and opt-in native test suites. |
| [GitHub workflows](../.github/workflows/ci.yml) | General-runner matrix, a frontend/backend job with runtime dependencies installed, and a native job that builds and runs the example suite with Clang. |

## Root files

| File | Responsibility |
| --- | --- |
| [Launcher](../kinetic.py) | The build and run command-line entry point. |
| [Package configuration](../pyproject.toml) | Packages the compiler directory directly and defines the installed command. |
| [Requirements](../requirements.txt) | The runtime Python dependency list. |
| [Overview](../README.md) | Introduction and quick start. |
| [Installation](../INSTALL.md) | Toolchain setup and command usage. |
| [Contributing](../CONTRIBUTING.md) | Development practices and verification workflows. |
| [Agent guidance](../AGENTS.md) | Shared instructions for coding agents. |
| [Fallback agent guidance](../AGENT.md) | Alternative entry point for tools using the singular filename; points to the shared instructions. |
| [Claude Code guidance](../CLAUDE.md) | Claude Code's repository instructions. |
| [Roadmap](../ROADMAP.md) | Completed work, current priorities, and future milestones. |
| [License](../LICENSE) | Project licensing. |

The compiler sources remain a flat package in release 1.2.2. The
[bootstrap host interface](bootstrap_interface.md) lives in documentation because
it is a design contract, not an implemented runtime package. Its current-syntax
examples belong alongside the other numbered programs, with intentional
compile-time failures, runtime bounds failures, and warnings in their own example
subdirectories. The length builtin and runtime guards are implemented in the
existing analyzer/backend modules; they do not require a new package layer.

[Ignore rules](../.gitignore) cover Python/package caches, generated IR, native
objects, Windows debug/link outputs, and known extensionless example binaries.
Source programs and their documentation remain tracked.

## Working rules

- Keep compiler modules directly in the compiler package, with package-relative imports.
- Keep command-line launchers thin; pipeline logic belongs in the compilation API.
- Put runnable sample programs in the examples directory.
- Put maintenance commands in tools, not in the compiler pipeline.
- Add directories only when there is a real implementation to put in them.

The [architecture guide](architecture.md) explains how the compiler modules
interact. The roadmap describes future work without presenting it as existing
compiler functionality.
