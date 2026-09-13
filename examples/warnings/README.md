# Warning examples

These Kinetic 1.2.1 examples demonstrate nonfatal diagnostics. The compiler emits warnings to
stderr to point out code that is probably not what you intended.

Build any of them with:

```shell
python kinetic.py build examples/warnings/unused_variable.kn
```

You will see output shaped like:

```text
kinetic: warn: <line>:<column>: <message>
kinetic: N warning(s) emitted
Building ...
Build successful!
```

| Program | Warning it demonstrates |
| --- | --- |
| [unused_variable.kn](unused_variable.kn) | A binding that is declared but never read. |
| [shadowing.kn](shadowing.kn) | An inner declaration that reuses (shadows) an outer name. |

Warnings alone do not stop the build; unrelated compiler or toolchain errors
still can. A warning is not proof that a program is correct or memory-safe.
See [errors](../errors/README.md) for fatal diagnostic demonstrations and the
[frontend suite](../../tests/test_frontend.py) for warning coverage.

The [status-handling example](../06_status_handling.kn) is different: it prints
application-level success/failure messages using ordinary program logic. Those
messages are not compiler warnings or errors.

A failed [runtime bounds check](../runtime_errors/README.md) is also not a
warning: it terminates the executable unsuccessfully. Length queries count as
uses of array bindings and should not produce an unused-binding warning by themselves.
