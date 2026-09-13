# Kinetic roadmap

## Goal

Kinetic's next major destination is **self-hosting**: a compiler written in
Kinetic that can compile its own source and build a working successor compiler.

The current compiler is a Python 1.2.1 prototype. It is not self-hosting, and no
compiler stage has been ported to Kinetic yet. The language and runtime need
additional capabilities before that port is practical.

This roadmap is ordered by dependencies, not release dates. An implemented
prototype feature is not a promise of production readiness or memory safety.

## Done — implemented foundations

- [x] Lexer with keywords, literals, comments, and source locations.
- [x] Recursive-descent parser and an abstract syntax tree.
- [x] Function calls, type inference, and implicit function returns.
- [x] Immutable bindings, opt-in mutation, conditional branches, and loops.
- [x] Integer arithmetic, equality and ordered comparisons, string literals,
  and integer-array literals with indexed reads.
- [x] Printing builtin accepting one integer or string.
- [x] LLVM IR generation and verification through llvmlite.
- [x] Command-line build and run workflows using Clang for native executables.
- [x] A flat compiler package, example programs, user documentation, and agent guidance.
- [x] Static checks for repository layout, Python syntax, imports, and documentation.
- [x] Structured compile-time diagnostics: located `error: line:column` output,
  migration hints for removed syntax, unused-variable and shadowing warnings,
  constant array-bounds errors, and pluralized warning summaries.

See the [syntax guide](docs/syntax_guide.md) for the current language and the
[architecture guide](docs/architecture.md) for the implementation. Frontend
behavioral tests run without any external dependency. Backend tests require
llvmlite and run when it is installed; native tests additionally require Clang
and opt in through an environment flag, which hosted CI sets. See
[test commands](tests/README.md) for static-only work.

## In progress

### Declaration syntax and CI rollout

The compiler sources, examples, and guides now use
[`func`](compiler/lexer.py:33), [`let`](compiler/lexer.py:34), and standalone
[`mut`](compiler/lexer.py:35). The [Hello World example](examples/01_hello.kn)
shows the function declaration in a complete program.

The [GitHub workflow](.github/workflows/ci.yml) runs the shared general test
runner on Windows and Linux without installing llvmlite. A separate Ubuntu job
installs the dependency and runs frontend/backend tests. A third Ubuntu job
enables native testing and uses the runner-provided Clang toolchain to build
and execute every numbered example, the array metadata checks, and the
runtime-failure programs with nonzero-exit expectations. Use the results of the
corresponding hosted run to establish which checks actually passed.

### Array sizes, lifetimes, and runtime checks

The 1.2.0 implementation added a pointer/count array representation, an
integer-array length builtin, and runtime lower/upper-bound checks before
indexed reads. Metadata travels through copies, reassignment, and function calls.
The [byte-processing](examples/07_byte_processing.kn) and
[array-length](examples/08_array_lengths.kn) programs exercise these changes.

Version 1.2.1 fixes returned-array lifetimes with heap-allocated element storage
that lives until process exit. Failed allocations for nonempty arrays trap
before initialization; empty arrays remain valid length-zero values.

Frontend, LLVM-structure, native-output, runtime-failure, and CLI-exit regression
tests are defined, and the hosted native CI job executes the native suites on
every push. These changes implement size queries, guarded reads, and
heap-allocated process-lived element storage; they do not provide resizable
storage, indexed mutation, host services, storage reclamation, or a general
lifetime-safety model.

### Remaining preparation

The current focus is identifying the smallest coherent language and runtime
needed to implement a compiler. This is planning work, not an active compiler
port or an implemented runtime expansion.

- Define the bootstrap subset and the order in which its missing capabilities
  should be added.
- Identify representations for tokens, syntax trees, types, symbol tables, and
  generated output.
- Decide the allocation, lifetime, and host-runtime boundaries those structures need.
- Define the behavioral tests and bootstrap checks required to demonstrate success.

**Planning is complete when:** the subset, runtime interfaces, and acceptance
tests have concrete specifications. The milestones below are the proposed
sequence; their implementations remain future work.

## Milestones toward self-hosting

### 1. Establish a reliable bootstrap compiler

- [x] Add automated lexer, parser, analyzer, and code-generation regression tests
  ([frontend](tests/test_frontend.py), [backend](tests/test_backend.py)).
- [x] Add expected diagnostics for invalid programs (located errors, migration
  hints, warning emission, and summary pluralization).
- [x] Add focused regressions for scoping, inference, immutability, constant array
  bounds, and error handling in the existing language.
- [x] Specify prototype array lifetimes and add regression coverage for returned
  local arrays, dynamic bounds, and function results. Element storage is
  heap-allocated in 1.2.1, lives until process exit, and is never reclaimed.
- [x] Define the supported toolchain versions (llvmlite constrained to the 0.45 series in
  [requirements.txt](requirements.txt), Python 3.10+, Clang for native builds)
  and a repeatable verification workflow ([static, behavioral, and native CI](.github/workflows/ci.yml)).
- [x] Configure hosted CI to build and run the native example suite with Clang and native
  testing enabled; the Ubuntu native job exercises every numbered example and
  the runtime-failure programs on each push.

**Verification coverage:** the shared frontend, backend, and native suites cover
returned local arrays, dynamic bounds, and function results and are enabled in
hosted CI. The allocation-failure trap is implemented, but the current suites
do not force allocator failure. Passing verification must be established from
observed local or hosted results, not from configuration or written tests alone.

### 2. Add the language and runtime building blocks

- [ ] Source-text operations: lengths, byte or character access, comparison,
  slicing, and construction of output strings.
- [ ] Data structures suitable for compiler records and variants, growable
  buffers, and symbol lookup; choose the minimum useful design before adding features.
- [ ] Mutable indexed storage.
- [ ] Validate and close explicit collection-size handling and runtime read
  guards: the length builtin, array metadata, and read checks are implemented
  since 1.2.0 and covered by the suites selected in hosted CI. Version 1.2.1
  defines process-lived, unreclaimed heap storage and traps on failed nonempty
  allocations; mutation rules and allocation-failure regression coverage remain.
- [ ] Defined allocation and lifetime rules for compiler-owned data, with checks
  appropriate to the chosen design.
- [ ] File input/output, command-line arguments, diagnostics, and error/status reporting.
- [ ] Multi-file organization and a way to resolve compiler modules.
- [x] A documented interface to native services and the LLVM/Clang toolchain
  that does not require Python-specific llvmlite APIs inside Kinetic code
  ([bootstrap host interface](docs/bootstrap_interface.md)). This completes the
  design contract only; the adapter, language bindings, and acceptance tests
  remain unimplemented.

**Complete when:** Kinetic programs can read source files, build and traverse
compiler data structures, report errors, and write generated output with tested
resource-management behavior. This does not by itself establish production memory safety.

### 3. Implement the compiler in Kinetic incrementally

- [ ] Write a lexer in Kinetic and compare its results with the Python implementation.
- [ ] Port parsing and syntax-tree construction.
- [ ] Port semantic analysis and type checking.
- [ ] Implement code generation and a build driver using the agreed toolchain interface.
- [ ] Run the same language and diagnostic regression suites against both implementations.

The Python compiler remains the bootstrap implementation during this work.
Port one stage at a time, and establish parity before replacing a working stage.
Textual LLVM IR remains a possible output; the backend interface must be decided
and tested before the port depends on it.

**Complete when:** the Python compiler can build a Kinetic-written compiler that
compiles the agreed language subset and passes its regression suite.

### 4. Demonstrate a repeatable self-hosting cycle

- [ ] Use the Python bootstrap compiler to build the Kinetic compiler: stage 1.
- [ ] Use stage 1 to compile the same compiler sources: stage 2.
- [ ] Use stage 2 to rebuild the compiler and run the regression suite without
  using the Python compiler for those compilations.
- [ ] Compare deterministic generated output across rebuilds, accounting explicitly
  for any non-semantic build metadata.
- [ ] Document the bootstrap procedure, retained bootstrap version, and recovery path.

**Self-hosting is achieved when:** the Kinetic-written compiler rebuilds itself
and the resulting compiler passes the required behavior tests. LLVM, Clang,
and native runtime dependencies may remain; self-hosting does not mean rewriting
the entire native toolchain in Kinetic.

## After self-hosting

- [ ] Improve diagnostics, tooling, performance, and platform coverage.
- [ ] Evolve runtime and library facilities based on real compiler and user workloads.
- [ ] Maintain a reproducible bootstrap path as the language evolves.

Update this document when implementation and verification change a milestone's
status. Do not treat a planned capability as part of the current language.
