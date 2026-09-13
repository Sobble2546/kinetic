# Tests

Kinetic 1.2.1 has separate suites for repository structure, frontend behavior,
LLVM generation, and native execution. The native suite runs in hosted CI on
every push and stays opt-in locally. Run commands below from the repository root.

## Static-only checks

```shell
python -B -m unittest discover -s tests -p test_layout.py -v
```

The [layout suite](test_layout.py) requires only Python and does not import
Kinetic, generate IR, invoke Clang, or execute Kinetic programs. It covers:

- Flat compiler package structure and the expected example files.
- Python syntax, internal import targets, token references, and keyword mapping.
- Public exports and CLI entry points.
- The published Hello World program and declaration syntax in valid examples.
- Intentional old-syntax examples kept separate from valid programs.
- Local Markdown links, shared agent guidance, and workflow action references.

It is not a full YAML/Actions validator or a compiler-behavior test suite. Use
this explicit command whenever compilation or program execution is prohibited.

## Frontend behavior

```shell
python -B -m unittest discover -s tests -p test_frontend.py -v
```

The [frontend suite](test_frontend.py) imports the lexer, parser, and analyzer
without needing llvmlite or Clang. It covers locations, migration diagnostics,
declarations, precedence, entry-point checks, parameter errors, mutability,
scope-aware warnings, array-length tracking, and deferred function inference.
It also analyzes all nine numbered examples and checks intentional failures
and warning examples. This executes compiler frontend code, but does not emit
IR or run generated programs.

Length-builtin tests cover valid/empty arrays, invalid types and arity, reserved
function names, inference from array parameters and forward results, and dynamic
indexes left for runtime checks. A mocked CLI test checks successful exits,
nonzero child exits, and signal-termination mapping without building or spawning
a native program.

## LLVM backend behavior

```shell
python -B -m unittest discover -s tests -p test_backend.py -v
```

The [backend suite](test_backend.py) requires llvmlite and skips when unavailable.
It generates verified IR for every top-level example, checks Hello World output
content in IR, tests inferred function results, and inspects collected warnings.
It does not recursively include intentionally invalid diagnostic examples.
Discovery requires a nonempty example set rather than a hard-coded file count.
This is compilation to IR, even though it does not build or run native binaries.

Array tests inspect metadata construction/extraction, aggregate stores/loads,
forwarding, empty arrays, shadowing, control-flow integration, and heap
allocation of element storage. Structural LLVM assertions check that the bounds
failure block traps and that element pointer arithmetic and loads appear only
after the bounds branch. These backend tests require IR generation; they are
not part of static-only verification.

The backend also traps on failed nonempty-array allocations, but the current
suites do not force allocation failure or directly assert that failure path.
Do not describe the heap-storage tests as allocation-failure coverage.

## General runner

```shell
python -B tools/check.py
```

The [runner](../tools/check.py) discovers all suites. Backend tests run
automatically when llvmlite is installed; only native execution has a separate
opt-in flag. Therefore the runner is **not** appropriate for static-only tasks.

## Native examples — opt-in locally, enforced in CI

The [native suite](test_native.py) requires Clang and llvmlite. It runs in
hosted CI on every push; locally it is skipped unless native tests are enabled
and Clang is available, and opting in without llvmlite is not supported. Each
test builds in a temporary directory and checks an expected output fragment.
Coverage includes all nine numbered examples, including the status-handling,
byte-processing, and returned-array lifetime demonstrations.

Additional native tests check lengths and successful reads across function calls,
copies, and reassignment, including locally created arrays returned from helpers
and read after later calls; they also check nonzero exits for negative,
upper-bound, empty-array, shortened-array, and out-of-bounds returned-array
accesses. Runtime-failure examples are compiled and executed separately. Trap
status is checked as nonzero rather than assuming a specific platform's signal
number.

PowerShell:

```powershell
$env:KINETIC_NATIVE_TESTS = "1"
python -B -m unittest discover -s tests -p test_native.py -v
Remove-Item Env:KINETIC_NATIVE_TESTS
```

Unix-like shell:

```shell
KINETIC_NATIVE_TESTS=1 python -B -m unittest discover -s tests -p test_native.py -v
```

These commands compile and execute programs. Do not use them during static-only
work; the hosted native CI job already runs this suite with Clang on each push.
Expected outputs and written tests are not execution evidence — treat a green
hosted native job as the record of observed native behavior.

## CI and evidence

The [workflow](../.github/workflows/ci.yml) runs the general runner in its
Windows/Linux Python 3.10/3.14 matrix without installing llvmlite. A separate
Ubuntu Python 3.10 job installs the runtime dependency and runs frontend/backend
tests. A third Ubuntu job enables native testing and uses the runner-provided
Clang toolchain to build and execute every numbered example, the array metadata
checks, and the runtime-failure programs with nonzero-exit expectations.

Report passed, failed, and skipped suites separately. A green layout check does
not prove compiler behavior. Only an observed passing native run verifies the
covered native behavior; a skipped suite or configured job does not. Keep future
regression tests in these shared suites instead of duplicating assertions in CI.
