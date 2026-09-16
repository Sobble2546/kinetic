# Bootstrap host interface specification

## Status and scope

**Status: specification only.** This document defines the native-service
interface planned for the Kinetic-written compiler. It covers buffers, file
access, process arguments, and toolchain invocation. The host adapter has not
been implemented; the current compiler is described in [architecture](architecture.md).

The proposed target is a single-process, single-compilation driver that emits
textual LLVM IR and invokes Clang through a small native host adapter. Compiler
logic must not depend on Python objects or llvmlite APIs. The initial adapter
uses the target's C calling convention; it does not expose LLVM's in-process API.
The eventual foreign-call syntax is a separate language-design task.

## Examples using current features

- [Status-code handling](../examples/06_status_handling.kn): a self-contained
  validator returns success or failure, and the caller handles the result.
- [Byte processing](../examples/07_byte_processing.kn): an integer array,
  length queries, and checked reads are used to count ASCII digits.
- [Array lengths](../examples/08_array_lengths.kn): length metadata follows
  arrays through function calls and reassignment.

These examples use implemented Kinetic features to demonstrate the concepts.
They do not call the proposed host adapter. Expected outputs are listed in the
[example catalog](../examples/README.md).

Kinetic 1.3.0's pointer/count array aggregate is internal to generated programs;
it is not an opaque host handle and provides no generation validation or session
ownership. The host ABI design version remains 1 and is independent of the
compiler release number. Current arrays use unreclaimed, process-lived heap
storage and trap on failed nonempty allocations; they do not return recoverable
allocation-status values. These rules, length queries, and range checks do not
implement the session ownership, reclamation, or status requirements below.

## Responsibilities

| Component | Owns |
| --- | --- |
| Kinetic-written compiler | Lexing, parsing, type analysis, diagnostics, symbol naming, and textual IR generation. |
| Native host adapter | Checked buffers, file access, process arguments, diagnostic output, and launching the configured toolchain. |
| Clang and LLVM | Parsing and validating submitted IR, native code generation, and linking. |

The host adapter cannot repair invalid language semantics or infer missing user
intent. Compiler errors prevent the toolchain invocation. A successful Clang
invocation is not proof that the emitted program is semantically correct or safe.

## ABI value and ownership rules

- Status values are signed 32-bit integers. Zero means success; nonzero means
  failure. Portable categories are invalid argument, invalid handle, bounds
  failure, allocation failure, I/O failure, tool unavailable, tool failure,
  timeout, and unsupported target. Platform error details are diagnostic data,
  not portable status values.
- Buffer handles are opaque unsigned 64-bit identifiers. Zero is invalid; the
  adapter checks both identity and generation so a released handle cannot refer
  to a later allocation. Handles are not addresses and must not be dereferenced.
- Lengths and offsets are unsigned 64-bit byte counts. The adapter checks host
  address-space limits and arithmetic overflow before allocation or indexing.
- Byte values are integers from 0 through 255. Text encoding is UTF-8, but
  source files and generated output are stored as byte buffers, without newline
  normalization or implicit terminators.
- Each operation returns a status. Scalar results and new handles are written
  into caller-owned output slots; failed operations set these results to zero.
  No native structures, exceptions, or allocator-owned pointers cross the ABI.
- One compilation session owns every buffer it creates. Borrowed input handles
  remain caller-owned. Operations do not retain borrowed handles after returning.
  Closing the session frees remaining buffers; explicit release invalidates a
  handle immediately. Double release reports invalid handle.
- Mutating operations either succeed fully or leave the existing buffer
  unchanged. Access to a released buffer, invalid range, or failed allocation
  returns an error rather than silently truncating output.

These are requirements for the future adapter, not guarantees of the current
array implementation. Start with session-scoped storage; a general-purpose
language memory model is outside this interface's scope.

## Required operations

Names in this table describe logical operations, not existing language builtins.
All operations follow the status/result convention above.

| Operation | Inputs | Results and required behavior |
| --- | --- | --- |
| Open session | Memory budget in bytes | New session; rejects unsupported budgets. |
| Close session | Session | Releases resources; a closed session cannot be reused. |
| Create buffer | Session, initial capacity | New empty owned buffer, limited by the session budget. |
| Release buffer | Session, handle | Invalidates the handle and frees its allocation. |
| Buffer length | Session, handle | Current length, distinct from capacity. |
| Read byte | Session, handle, offset | Byte at an offset strictly smaller than the length. |
| Append byte | Session, handle, byte value | Adds one byte, growing within the budget. |
| Append range | Session, destination, source, offset, count | Copies a valid source range; self-append behaves as a snapshot of the original range. |
| Compare buffers | Session, left, right | Signed result: -1, 0, or 1, using unsigned-byte lexicographic ordering. |
| Copy slice | Session, source, offset, count | New owned buffer; allows an empty slice at the end. |
| Read source | Session, path buffer | New owned buffer containing the complete file bytes. No partial result on failure. |
| Write output | Session, path buffer, content buffer | Writes through a sibling temporary file, then replaces the requested output only on success. |
| Argument count | Session | Number of user arguments, excluding the executable name. |
| Argument copy | Session, index | New owned UTF-8 buffer for one argument. |
| Write diagnostic | Session, content buffer | Writes all bytes to standard error, handling partial writes. Content is data, never a format string. |
| Build native output | Session, IR path, output path, configured tool path, target, timeout | Tool exit status; success requires exit zero and the expected output artifact. |

Paths and arguments containing embedded NUL bytes are invalid. Windows paths
are converted from UTF-8 to the native wide-character representation; invalid
encoding fails explicitly. On Unix-like hosts, this initial interface supports
UTF-8 paths only and must report unrepresentable arguments rather than corrupt
them. The build operation accepts only targets supported by the adapter's
configuration; the first implementation need only support host-native builds.

## Native build protocol

1. Read and validate source, perform semantic analysis, and collect diagnostics.
   Stop on errors; warnings alone do not prevent a build.
2. Generate complete textual IR in an owned buffer. The selected target triple,
   pointer width, and data layout must agree with the configured Clang toolchain.
   Reject an unsupported target before generating target-dependent IR.
3. Write IR into a unique build workspace through the output operation. Use
   absolute input and output paths, including for filenames beginning with a dash.
4. Launch the configured Clang executable with an argument vector: IR language
   selection, IR path, explicit target, and an output path inside the workspace.
   Do not invoke a shell or concatenate source-derived command text. Any extra
   flags come from explicit trusted configuration, not source contents.
5. Forward tool diagnostics to standard error without interpreting their content.
   Inherit the diagnostic stream rather than using an undrained pipe. Close
   unrelated file handles in the child. A timeout terminates and reaps the child
   process group/job and returns timeout, never success.
6. Treat IR rejection, link failure, nonzero termination, missing output, and
   launch failure as build failures. Preserve an existing requested executable
   on failure. On success, publish the temporary executable into the requested
   destination on the same filesystem using atomic replacement where supported;
   otherwise report unsupported publication rather than silently weakening it.
7. Release temporary resources on every path. Build mode never runs the result.
   A future run command must request execution separately and propagate its
   exit status without translating a nonzero result into success.

The adapter uses an explicitly selected tool path and records its version and
target in the build report. The future bootstrap workflow must pin a tested
combination rather than assume every Clang version accepts the same LLVM IR.
Clang handles IR parsing/verification during the build; no Python-only
verification step is required by the self-hosted compiler.

## Implementation order and acceptance gates

| Gate | Required evidence before completion |
| --- | --- |
| Buffer adapter | Tests for zero-length buffers, overflow, budget exhaustion, invalid/stale handles, boundary reads, self-append, and failure atomicity. |
| Text and host I/O | Exact-byte round trips, Unicode paths, NUL rejection, denied access, missing files, partial-write handling, argument copying, and diagnostic write failures. |
| Tool driver | Tests with a controlled fake tool for paths containing spaces or shell metacharacters, nonzero exits, timeout, launch failure, missing output, and preservation of existing output. |
| LLVM integration | Real pinned-toolchain tests for valid IR, malformed IR, linking failure, target mismatch, and an executable with the expected exit status and output. |
| Kinetic integration | Compiler lowering for each host operation plus language tests for successful and failed calls. No Python service may be required by the resulting executable. |
| Bootstrap | Build stage 1 with the Python compiler, rebuild with stage 1 and stage 2, compare deterministic outputs, and run the same behavioral suite at each stage. |

Passing documentation checks validates links and repository structure only.
All implementation gates above remain pending until their tests actually run
successfully. This design does not complete the broader runtime-building-block
milestone or demonstrate self-hosting.

See the [roadmap](../ROADMAP.md) for the separate implementation milestones and
[contributing](../CONTRIBUTING.md) for verification constraints.
