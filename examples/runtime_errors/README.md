# Runtime bounds failures

These 1.2.1 programs are intentionally **not** success examples. Their index
expressions pass compile-time analysis, but the generated executable terminates
at a bounds check before accessing an invalid element.

| Program | Reason for termination |
| --- | --- |
| [Upper bound](out_of_bounds.kn) | The index equals the array's length. |
| [Negative index](negative_index.kn) | The index is below zero. |

When native execution is permitted:

```shell
python kinetic.py run examples/runtime_errors/out_of_bounds.kn
```

The backend emits an LLVM trap followed by an unreachable terminator on the
failure path. The process exits unsuccessfully; the exact signal or exit code
is platform-dependent. This is not a formatted compile-time diagnostic and does
not guarantee a human-readable runtime message. The CLI reports failure through
its exit status. Nothing after the invalid access is executed.

The [native suite](../../tests/test_native.py) includes nonzero-exit checks for
these examples. They are not run during static-only verification. Compare the
[compile-time failures](../errors/README.md), which are rejected before IR
generation. Bounds checks do not solve dangling array storage or provide a
production memory-safety model. Version 1.2.1 separately fixes returned-array
lifetimes with unreclaimed heap storage and traps on failed nonempty-array
allocations; these examples test bounds failures, not allocation failure.
