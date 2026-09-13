# Error examples

These Kinetic 1.2.1 examples **fail to compile on purpose**. Each demonstrates a specific
compile-time error so you can see what the diagnostic looks like.

Build any of them with:

```shell
python kinetic.py build examples/errors/immutable_reassign.kn
```

You will see output shaped like:

```text
kinetic: error: <line>:<column>: <message>
```

| Program | Error it demonstrates |
| --- | --- |
| [immutable_reassign.kn](immutable_reassign.kn) | Reassigning a `let` binding — only `mut` bindings can change. |
| [out_of_bounds.kn](out_of_bounds.kn) | A constant index past the end of a known-length array literal. |
| [missing_main.kn](missing_main.kn) | A program with no `main` entry point. |
| [old_fn_keyword.kn](old_fn_keyword.kn) | The removed `fn` keyword; the lexer reports the migration to `func`. |
| [old_let_mut.kn](old_let_mut.kn) | The removed `let mut` form; mutable bindings use standalone `mut`. |
| [undefined_variable.kn](undefined_variable.kn) | Using a name that was never declared. |
| [type_mismatch.kn](type_mismatch.kn) | Mixing an integer and a string in arithmetic. |
| [main_parameters.kn](main_parameters.kn) | Declaring parameters on the fixed no-argument `main` entry point. |
| [duplicate_parameters.kn](duplicate_parameters.kn) | Declaring the same parameter name twice in one function. |
| [len_type.kn](len_type.kn) | Passing an integer instead of an integer array or string to the length builtin. |
| [len_arity.kn](len_arity.kn) | Calling the length builtin without its required argument. |

See [warnings](../warnings/README.md) for diagnostics that do **not** stop
compilation.

The historical syntax-removal examples retain the release in which the old
keywords were removed. The [frontend suite](../../tests/test_frontend.py) checks
their expected diagnostics without generating native binaries. These programs
must not be included in success-only example build loops.

The [runtime-failure examples](../runtime_errors/README.md) differ: their indexes
are not rejected by constant analysis, so the emitted program traps when it
reaches an invalid read. A runtime trap is not a compile-time diagnostic.
