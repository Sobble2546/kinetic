import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLANG = shutil.which("clang")
RUN_NATIVE = os.environ.get("KINETIC_NATIVE_TESTS") == "1"

EXPECTED = {
    "01_hello.kn": "Hello World!",
    "02_logic.kn": "We hit the lucky number 3!",
    "03_arrays.kn": "Math and arrays work perfectly!",
    "04_bounds_checked.kn": "Highest score:\n90\nLowest score:\n77\n",
    "05_mutability.kn": "Kinetic\nKinetic\nKinetic\nFinal count:\n3\n",
    "06_status_handling.kn": "Byte accepted\nInvalid byte\n",
    "07_byte_processing.kn": "ASCII digits:\n3\n",
    "08_array_lengths.kn": "Array lengths:\n3\n2\n3\n0\n2\n",
    "09_array_lifetimes.kn": (
        "Scratch array:\n40\nReturned array:\n7\n8\n9\nReturned length:\n3\n"
    ),
    "10_text.kn": "Text operations:\n7\n75\nKin\nHello, Kinetic!\nequal\nordered\n",
}


@unittest.skipUnless(CLANG, "clang is not installed")
@unittest.skipUnless(RUN_NATIVE, "set KINETIC_NATIVE_TESTS=1 to run native builds")
class NativeExampleTests(unittest.TestCase):
    def test_examples_build_and_run(self):
        from compiler.compiler import compile_source

        for name, expected_output in EXPECTED.items():
            with self.subTest(example=name):
                source = Path("examples") / name
                with tempfile.TemporaryDirectory() as directory:
                    work = Path(directory) / name
                    work.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                    llvm_ir = compile_source(work.read_text(encoding="utf-8"))
                    ll_file = work.with_suffix(".ll")
                    ll_file.write_text(llvm_ir, encoding="utf-8")
                    binary = work.with_suffix(
                        ".exe" if sys.platform == "win32" else ""
                    )
                    subprocess.run(
                        ["clang", str(ll_file), "-o", str(binary)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    result = subprocess.run(
                        [str(binary)], capture_output=True, text=True, check=True
                    )
                    self.assertIn(expected_output, result.stdout)

    def _run_source(self, source):
        from compiler.compiler import compile_source

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ir_path = work / "program.ll"
            ir_path.write_text(compile_source(source), encoding="utf-8")
            binary = work / ("program.exe" if sys.platform == "win32" else "program")
            subprocess.run(
                [CLANG, str(ir_path), "-o", str(binary)],
                capture_output=True, text=True, check=True, timeout=30,
            )
            return subprocess.run(
                [str(binary)], cwd=directory, capture_output=True, text=True, timeout=10
            )

    def test_lengths_and_reads_survive_copies_calls_and_branches(self):
        result = self._run_source(
            "func count(values) { len(values) }\n"
            "func forward(values) { values }\n"
            "func read_at(values, index) { values[index] }\n"
            "func main() {\n"
            "  let original = [10, 20, 30]\n"
            "  mut values = original\n"
            "  print(count(values))\n"
            "  if 1 < 2 { values = [40, 50] } else { values = [60] }\n"
            "  print(len(values))\n"
            "  print(len(original))\n"
            "  print(read_at(forward(values), 1))\n"
            "  values = []\n"
            "  print(len(values))\n"
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "3\n2\n3\n50\n0\n")

    def test_bounds_failures_terminate_without_reaching_following_code(self):
        cases = {
            "negative": "let values = [10] let index = 0 - 1",
            "upper": "let values = [10] let index = len(values)",
            "empty": "let values = [] let index = 0",
            "shrunk": "mut values = [10, 20] values = [30] let index = 1",
            "branch": "mut values = [10, 20] if 1 < 2 { values = [30] } let index = 1",
        }
        for name, setup in cases.items():
            with self.subTest(case=name):
                result = self._run_source(
                    "func read_at(values, index) { values[index] }\n"
                    "func main() { " + setup + ' print(read_at(values, index)) print("Unreachable") }'
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Unreachable", result.stdout)

    def test_length_is_reloaded_after_reassignment_in_loop(self):
        result = self._run_source(
            "func main() { mut values = [10, 20, 30] mut index = 0\n"
            "  while index < len(values) {\n"
            "    print(values[index])\n"
            "    values = [40]\n"
            "    index = index + 1\n"
            "  }\n"
            "  print(len(values))\n"
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "10\n1\n")

    def test_length_evaluates_argument_once_and_handles_shadowing(self):
        result = self._run_source(
            "func observe(values) { print(99) values }\n"
            "func main() { mut values = [1, 2]\n"
            "  print(len(observe(values)))\n"
            "  if 1 < 2 { let values = [7] print(len(values)) print(values[0]) }\n"
            "  print(len(values))\n"
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "99\n2\n1\n7\n2\n")

    def test_returned_local_array_survives_later_calls(self):
        result = self._run_source(
            "func make() { [7, 8, 9] }\n"
            "func clobber() { let scratch = [40, 41, 42, 43, 44, 45, 46, 47] print(scratch[0]) }\n"
            "func main() {\n"
            "  let values = make()\n"
            "  clobber()\n"
            "  print(values[0])\n"
            "  print(values[2])\n"
            "  print(len(values))\n"
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "40\n7\n9\n3\n")

    def test_array_results_through_branches_and_calls(self):
        result = self._run_source(
            "func pick(flag) { if flag > 0 { [1, 2] } else { [3] } }\n"
            "func main() {\n"
            "  let a = pick(1)\n"
            "  let b = pick(0)\n"
            "  print(len(a))\n"
            "  print(a[1])\n"
            "  print(len(b))\n"
            "  print(b[0])\n"
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "2\n2\n1\n3\n")

    def test_bounds_guard_applies_to_returned_arrays(self):
        result = self._run_source(
            "func make() { [5, 6] }\n"
            "func main() { let values = make() let index = len(values) print(values[index]) print(\"Unreachable\") }"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Unreachable", result.stdout)

    def test_runtime_failure_examples_exit_unsuccessfully(self):
        root = Path(__file__).resolve().parents[1] / "examples" / "runtime_errors"
        for name in ("out_of_bounds.kn", "negative_index.kn"):
            with self.subTest(example=name):
                result = self._run_source((root / name).read_text(encoding="utf-8"))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Unreachable", result.stdout)

    def test_string_operations_produce_expected_values(self):
        result = self._run_source(
            "func main() {\n"
            '  let text = "Kinetic"\n'
            "  print(len(text))\n"
            "  print(text[0])\n"
            "  print(text[6])\n"
            '  print(slice(text, 0, 3))\n'
            '  print(slice(text, 3, len(text)))\n'
            '  print(text + " lang")\n'
            '  if "abc" < "abd" { print("lt") }\n'
            '  if "abc" == "abc" { print("eq") }\n'
            '  if "abd" > "abc" { print("gt") }\n'
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "7\n75\n99\nKin\netic\nKinetic lang\nlt\neq\ngt\n",
        )

    def test_string_results_survive_function_calls_and_branches(self):
        result = self._run_source(
            "func shout(text) { text + \"!\" }\n"
            "func first(text) { text[0] }\n"
            "func pick(flag) { if flag == 1 { \"left\" } else { \"right\" } }\n"
            "func main() {\n"
            '  print(shout("hi"))\n'
            '  print(first("AZ"))\n'
            "  print(pick(1))\n"
            "  print(pick(2))\n"
            '  print(shout(pick(1)))\n'
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "hi!\n65\nleft\nright\nleft!\n")

    def test_string_byte_reads_are_mutable_binding_compatible(self):
        result = self._run_source(
            "func main() {\n"
            '  mut text = "ab"\n'
            "  print(text[1])\n"
            '  text = "xy"\n'
            "  print(text[1])\n"
            "  print(len(text))\n"
            "}"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "98\n121\n2\n")

    def test_string_bounds_failures_terminate_without_reaching_following_code(self):
        cases = {
            "index_upper": 'let text = "ab" let index = 2 print(text[index])',
            "index_negative": 'let text = "ab" let index = 0 - 1 print(text[index])',
            "slice_end": 'print(slice("ab", 0, 3))',
            "slice_order": 'print(slice("ab", 2, 1))',
            "slice_negative": 'print(slice("ab", 0 - 1, 1))',
        }
        for name, body in cases.items():
            with self.subTest(case=name):
                result = self._run_source(
                    "func main() { " + body + ' print("Unreachable") }'
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Unreachable", result.stdout)


if __name__ == "__main__":
    unittest.main()
