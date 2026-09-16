# Compiler sources

This directory is Kinetic's Python package. All compiler stages and the CLI live
directly here, with one source file per concern. It implements Kinetic 1.3.0.

| Stage or concern | Source |
| --- | --- |
| Public package API | [Package initializer](__init__.py) |
| Pipeline orchestration and IR verification | [Compiler](compiler.py) |
| Lexing and token definitions | [Lexer](lexer.py), [tokens](tokens.py) |
| Parsing and syntax tree | [Parser](parser.py), [AST](ast.py) |
| Type checking and inference | [Analyzer](analyzer.py), [types](types.py) |
| LLVM code generation | [Backend](backend.py) |
| Diagnostics and source locations | [Diagnostics](diagnostics.py), [errors](errors.py) |
| Native build and run driver | [CLI](cli.py) |
| Module entry point | [Module launcher](__main__.py) |

Stage modules use package-relative imports. The orchestration entry point is
[`compile_with_diagnostics()`](compiler.py:7), returning verified textual IR and
warnings. [`compile_source()`](compiler.py:23) returns just the IR and is lazily
exported by the package initializer. Backend dependencies are imported only when
code generation is reached; frontend analysis can run without llvmlite.

The root [launcher](../kinetic.py), the module entry point, and the installed
command all use the same CLI. [pyproject.toml](../pyproject.toml) packages this
directory directly.

See the [architecture guide](../docs/architecture.md) for dependencies between stages.
The analyzer and backend jointly implement the array-length builtin. The backend
carries array pointers and element counts together and checks the index range
before every element read and indexed write. Mutable bindings store the whole
aggregate, and
function arguments/results use the same representation. Element storage is
heap-allocated at construction and lives until process exit; it is never
reclaimed, which is a prototype simplification rather than a safety model.
Nonempty-array allocations are checked for failure before any element is
initialized; failure traps. Empty arrays permit a null pointer and retain a
zero count. Indexed assignment writes through mutable bindings under the same
range guard, and copies share element storage, so aliases observe writes.

The [bootstrap host interface](../docs/bootstrap_interface.md) is a future design,
not an additional implementation in this package. Its
[concept examples](../examples/README.md) use existing compiler features only.
