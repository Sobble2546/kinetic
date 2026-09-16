# Claude Code guidance

@AGENTS.md

The shared [agent guidance](AGENTS.md) applies to Claude Code. It is the source of
truth for repository structure, compiler boundaries, and verification rules.

## Working context

- Kinetic is a 1.3.0 prototype compiler written in Python, using llvmlite and Clang.
- Compiler modules live directly in the [compiler package](compiler/README.md).
  Keep imports package-relative and avoid adding wrapper packages.
- The [root launcher](kinetic.py) delegates to the same CLI as the installed command.
- Use the [examples](examples/README.md) for documented build and run workflows.
- Consult [architecture](docs/architecture.md) and [contributing](CONTRIBUTING.md)
  before changing compiler stages or development tooling.

## Verification

For repository and documentation changes, use the static-only checker:

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

It needs only Python and does not import Kinetic, emit LLVM IR, invoke Clang, or
run Kinetic programs. When the user prohibits compilation or execution, do not
invoke the compilation API or native build commands, even as a smoke test.
Report skipped behavioral verification explicitly. Do not install dependencies
just to run these static checks.

The general [runner](tools/check.py) discovers behavioral tests too; do not use it
for static-only tasks. The [workflow](.github/workflows/ci.yml) has a general-test
matrix, a frontend/backend job with llvmlite installed, and a native job that
enables native testing and builds and runs the example suite with Clang. Keep
local and hosted test logic aligned.

## Roadmap discipline

Read [ROADMAP.md](ROADMAP.md) when planning language work. Self-hosting is a future
target, not an existing capability. Keep implemented functionality, planning,
and future work distinct; do not mark a milestone complete without evidence.
The 1.3.0 prototype does not provide a production memory-safety model. Array
lengths and runtime read guards are implemented; array element storage is
heap-allocated and lives until process exit without reclamation, which is a
deliberate leak rather than a general lifetime-safety model. Failed nonempty-array
allocations trap before initialization. Report behavioral verification based on
what actually passed: skipped suites and CI configuration alone are not passing
verification. Use the results of the corresponding hosted native run as evidence.

The [bootstrap contract](docs/bootstrap_interface.md) describes proposed native
services, not implemented functionality. Keep explanations in documentation and
examples rather than Python comments or docstrings.
