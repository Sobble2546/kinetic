# Kinetic documentation

The [bootstrap host interface](bootstrap_interface.md) documents the future
native-service and toolchain contract. Its services are not implemented yet.

| Guide | Audience |
| --- | --- |
| [Syntax guide](syntax_guide.md) | Language users learning the 1.3.0 feature set, including array lengths, process-lived storage, indexed writes, text operations, and runtime checks. |
| [Bootstrap host interface](bootstrap_interface.md) | Contributors implementing the proposed native-service boundary. |
| [Architecture](architecture.md) | Contributors following the compilation pipeline. |
| [Repository layout](repository_layout.md) | Contributors deciding where code and tooling belong. |
| [Installation](../INSTALL.md) | Users setting up the Python dependency and native toolchain. |
| [Contributing](../CONTRIBUTING.md) | Contributors choosing the appropriate verification workflow. |
| [Roadmap](../ROADMAP.md) | Contributors following current priorities and future self-hosting milestones. |
| [Examples](../examples/README.md) | Readers looking for complete, small Kinetic programs. |
| [Test suites](../tests/README.md) | Contributors choosing static-only versus behavioral verification. |

Language documentation stays separate from implementation and development tools.
The [syntax guide](syntax_guide.md) describes the implemented language; the
roadmap describes work that has not been implemented yet.

The [status-handling](../examples/06_status_handling.kn) and
[byte-processing](../examples/07_byte_processing.kn) programs illustrate the
bootstrap design using the current language. They are not host-service implementations.

The [array-length example](../examples/08_array_lengths.kn) demonstrates the
implemented builtin, while [runtime-failure examples](../examples/runtime_errors/README.md)
show reads that pass analysis but trap when executed. Version 1.2.1 keeps array
element storage alive until process exit and traps on failed nonempty-array
allocations. Storage is not reclaimed, and these fixes do not establish a
general memory-safety model.
