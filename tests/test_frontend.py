import unittest

from compiler.diagnostics import Diagnostics
from compiler.errors import CompileError, LexerError, ParseError
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.analyzer import TypeAnalyzer
from compiler.tokens import TokenKind


def tokenize(source):
    return Lexer(source, Diagnostics()).tokenize()


def parse(source):
    return Parser(tokenize(source)).parse()


def analyze(source):
    diagnostics = Diagnostics()
    program = parse(source)
    types = TypeAnalyzer(program, diagnostics).analyze()
    return types, diagnostics


class LexerTests(unittest.TestCase):
    def test_keywords_map_to_declaration_tokens(self):
        kinds = [token.kind for token in tokenize("func let mut")]
        self.assertEqual(
            kinds, [TokenKind.FUNC, TokenKind.LET, TokenKind.MUT, TokenKind.EOF]
        )

    def test_locations_track_line_and_column(self):
        tokens = tokenize("func main() {\n  mut x = 1\n}")
        mut_token = next(token for token in tokens if token.kind is TokenKind.MUT)
        self.assertEqual((mut_token.line, mut_token.column), (2, 3))

    def test_removed_fn_keyword_reports_migration_message(self):
        with self.assertRaises(LexerError) as raised:
            tokenize("fn main() { }")
        self.assertIn("func", str(raised.exception))
        self.assertEqual(raised.exception.line, 1)

    def test_unexpected_character_is_located(self):
        with self.assertRaises(LexerError) as raised:
            tokenize("let x = 1\nlet y = @")
        self.assertEqual((raised.exception.line, raised.exception.column), (2, 9))

    def test_string_escapes_decode(self):
        token = next(
            token for token in tokenize(r'print("a\nb")') if token.kind is TokenKind.STRING
        )
        self.assertEqual(token.value, "a\nb")


class ParserTests(unittest.TestCase):
    def test_declarations_parse_with_mutability(self):
        program = parse("func main() {\n  let a = 1\n  mut b = 2\n  b = 3\n}")
        statements = program.functions[0].body
        self.assertFalse(statements[0].is_mut)
        self.assertTrue(statements[1].is_mut)

    def test_let_mut_is_rejected_with_hint(self):
        with self.assertRaises(ParseError) as raised:
            parse("func main() {\n  let mut x = 1\n}")
        self.assertIn("mut name = value", str(raised.exception))

    def test_missing_func_keyword_is_located(self):
        with self.assertRaises(ParseError) as raised:
            parse("main() { }")
        self.assertIn("expected 'func'", str(raised.exception))
        self.assertEqual(raised.exception.line, 1)

    def test_unclosed_block_reports_eof_location(self):
        with self.assertRaises(ParseError) as raised:
            parse("func main() {\n  let x = 1\n")
        self.assertIn("unclosed block", str(raised.exception))
        self.assertEqual(raised.exception.line, 3)

    def test_operator_precedence(self):
        program = parse("func main() {\n  1 + 2 * 3\n}")
        expression = program.functions[0].body[0].expression
        self.assertEqual(expression.operator, "+")
        self.assertEqual(expression.right.operator, "*")


class AnalyzerTests(unittest.TestCase):
    def test_missing_main_is_an_error(self):
        with self.assertRaises(CompileError) as raised:
            analyze("func helper() {\n  1\n}")
        self.assertIn("no 'main' entry point", str(raised.exception))

    def test_empty_program_reports_missing_main(self):
        with self.assertRaises(CompileError) as raised:
            analyze("")
        self.assertIn("no 'main' entry point", str(raised.exception))

    def test_main_parameters_are_rejected_before_codegen(self):
        with self.assertRaises(CompileError) as raised:
            analyze("func main(value) {\n  print(value)\n}")
        self.assertIn("'main' entry point cannot have parameters", str(raised.exception))

    def test_duplicate_function_parameters_are_rejected(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func choose(value, value) {\n"
                "  value\n"
                "}\n"
                "func main() {\n"
                "  print(choose(1, 2))\n"
                "}"
            )
        self.assertIn("duplicate parameter 'value'", str(raised.exception))

    def test_immutable_reassignment_is_located(self):
        with self.assertRaises(CompileError) as raised:
            analyze("func main() {\n  let x = 1\n  x = 2\n}")
        self.assertIn("cannot reassign immutable variable", str(raised.exception))
        self.assertEqual(raised.exception.line, 3)

    def test_unused_variable_warns(self):
        _, diagnostics = analyze("func main() {\n  let x = 1\n}")
        rendered = diagnostics.render_warnings()
        self.assertEqual(len(rendered), 1)
        self.assertIn("warn", rendered[0])
        self.assertIn("never used", rendered[0])

    def test_shadowing_warns(self):
        _, diagnostics = analyze(
            "func main() {\n  let x = 1\n  if 1 == 1 {\n    let x = 2\n    print(x)\n  }\n  print(x)\n}"
        )
        rendered = diagnostics.render_warnings()
        self.assertTrue(any("shadows" in warning for warning in rendered))

    def test_constant_out_of_bounds_index_is_an_error(self):
        with self.assertRaises(CompileError) as raised:
            analyze("func main() {\n  let xs = [1, 2]\n  print(xs[2])\n}")
        self.assertIn("out of bounds", str(raised.exception))
        self.assertIn("length 2", str(raised.exception))

    def test_in_bounds_index_is_accepted(self):
        types, _ = analyze("func main() {\n  let xs = [1, 2]\n  print(xs[1])\n}")
        self.assertIn("main", types)

    def test_shadowed_array_length_restores_outer_binding(self):
        types, _ = analyze(
            "func main() {\n"
            "  let xs = [1, 2, 3]\n"
            "  if 1 == 1 {\n"
            "    let xs = [9]\n"
            "    print(xs[0])\n"
            "  }\n"
            "  print(xs[2])\n"
            "}"
        )
        self.assertIn("main", types)

    def test_shadowed_immutable_binding_does_not_inherit_mutability(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func main() {\n"
                "  mut x = 1\n"
                "  if 1 == 1 {\n"
                "    let x = 2\n"
                "    x = 3\n"
                "  }\n"
                "}"
            )
        self.assertIn("cannot reassign immutable variable", str(raised.exception))

    def test_array_reassignment_updates_known_length(self):
        types, _ = analyze(
            "func main() {\n"
            "  mut xs = [1, 2]\n"
            "  xs = [1, 2, 3]\n"
            "  print(xs[2])\n"
            "}"
        )
        self.assertIn("main", types)

    def test_array_reassignment_shrink_updates_bounds_error(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func main() {\n"
                "  mut xs = [1, 2, 3]\n"
                "  xs = [1]\n"
                "  print(xs[2])\n"
                "}"
            )
        self.assertIn("out of bounds", str(raised.exception))
        self.assertIn("length 1", str(raised.exception))

    def test_array_reassignment_from_binding_clears_stale_length(self):
        types, _ = analyze(
            "func main() {\n"
            "  mut xs = [1, 2]\n"
            "  let replacement = [1, 2, 3]\n"
            "  xs = replacement\n"
            "  print(xs[2])\n"
            "}"
        )
        self.assertIn("main", types)

    def test_forward_array_reassignment_clears_stale_length(self):
        types, _ = analyze(
            "func main() {\n"
            "  mut xs = [1]\n"
            "  let replacement = [1, 2, 3]\n"
            "  xs = identity(replacement)\n"
            "  print(xs[2])\n"
            "}\n"
            "func identity(value) {\n"
            "  value\n"
            "}"
        )
        self.assertEqual(types["identity"].parameters[0].name, "INT_ARRAY")
        self.assertEqual(types["identity"].result.name, "INT_ARRAY")

    def test_conditional_array_reassignment_drops_uncertain_length(self):
        types, _ = analyze(
            "func main() {\n"
            "  mut xs = [1, 2, 3]\n"
            "  if 1 < 2 {\n"
            "    xs = [1]\n"
            "  }\n"
            "  print(xs[2])\n"
            "}"
        )
        self.assertIn("main", types)

    def test_matching_if_else_array_lengths_remain_known(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func main() {\n"
                "  mut xs = [1, 2, 3]\n"
                "  if 1 < 2 {\n"
                "    xs = [1]\n"
                "  } else {\n"
                "    xs = [2]\n"
                "  }\n"
                "  print(xs[1])\n"
                "}"
            )
        self.assertIn("out of bounds", str(raised.exception))
        self.assertIn("length 1", str(raised.exception))

    def test_inner_shadow_use_does_not_hide_unused_outer_binding(self):
        _, diagnostics = analyze(
            "func main() {\n"
            "  let value = 1\n"
            "  if 1 == 1 {\n"
            "    let value = 2\n"
            "    print(value)\n"
            "  }\n"
            "}"
        )
        unused = [
            warning
            for warning in diagnostics.warnings
            if "never used" in warning.message
        ]
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].location.line, 2)

    def test_outer_use_does_not_hide_unused_inner_shadow(self):
        _, diagnostics = analyze(
            "func main() {\n"
            "  let value = 1\n"
            "  if 1 == 1 {\n"
            "    let value = 2\n"
            "  }\n"
            "  print(value)\n"
            "}"
        )
        unused = [
            warning
            for warning in diagnostics.warnings
            if "never used" in warning.message
        ]
        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].location.line, 4)

    def test_array_binding_copy_preserves_known_length(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func main() {\n"
                "  let source = [1, 2, 3]\n"
                "  let copy = source\n"
                "  print(copy[3])\n"
                "}"
            )
        self.assertIn("out of bounds", str(raised.exception))
        self.assertIn("length 3", str(raised.exception))

    def test_array_reassignment_from_binding_preserves_known_length(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func main() {\n"
                "  mut target = [1]\n"
                "  let source = [1, 2, 3]\n"
                "  target = source\n"
                "  print(target[3])\n"
                "}"
            )
        self.assertIn("out of bounds", str(raised.exception))
        self.assertIn("length 3", str(raised.exception))

    def test_print_waits_for_inferred_function_result(self):
        types, _ = analyze(
            "func identity(value) {\n"
            "  value\n"
            "}\n"
            "func main() {\n"
            "  print(identity(1))\n"
            "}"
        )
        self.assertEqual(types["identity"].parameters[0].name, "INT")
        self.assertEqual(types["identity"].result.name, "INT")

    def test_print_rejects_function_that_settles_to_void(self):
        with self.assertRaises(CompileError) as raised:
            analyze(
                "func noop() {\n"
                "}\n"
                "func main() {\n"
                "  print(noop())\n"
                "}"
            )
        self.assertIn("print expects one integer or string argument", str(raised.exception))

    def test_warning_summary_pluralization(self):
        _, diagnostics = analyze(
            "func main() {\n  let a = 1\n  let b = 2\n}"
        )
        self.assertEqual(diagnostics.summary(), "kinetic: 2 warnings emitted")

    def test_single_warning_summary_is_singular(self):
        _, diagnostics = analyze("func main() {\n  let a = 1\n}")
        self.assertEqual(diagnostics.summary(), "kinetic: 1 warning emitted")

    def test_type_mismatch_is_reported(self):
        with self.assertRaises(CompileError):
            analyze('func main() {\n  let x = 1 + "a"\n}')

    def test_print_rejects_wrong_argument_count(self):
        with self.assertRaises(CompileError) as raised:
            analyze("func main() {\n  print(1, 2)\n}")
        self.assertIn("print expects one integer or string argument", str(raised.exception))


class ArrayLengthTests(unittest.TestCase):
    def test_length_accepts_empty_and_nonempty_arrays(self):
        for value in ("[]", "[1, 2, 3]"):
            with self.subTest(value=value):
                types, diagnostics = analyze(
                    "func main() { let values = " + value + " print(len(values)) }"
                )
                self.assertEqual(types["main"].result.name, "INT")
                self.assertEqual(diagnostics.warnings, [])

    def test_length_rejects_wrong_types_and_arity_with_location(self):
        for argument in ("", "1", '"abc"', "1 == 1", "[], []", "print(1)"):
            with self.subTest(argument=argument):
                with self.assertRaises(CompileError) as raised:
                    analyze("func main() {\n  print(len(" + argument + "))\n}")
                self.assertIn("len expects exactly one integer array", str(raised.exception))
                self.assertEqual(raised.exception.line, 2)

    def test_length_infers_array_parameter_before_caller(self):
        types, _ = analyze(
            "func count(values) { len(values) }\n"
            "func main() { print(count([1, 2])) }"
        )
        self.assertEqual(types["count"].parameters[0].name, "INT_ARRAY")
        self.assertEqual(types["count"].result.name, "INT")

    def test_length_waits_for_forwarded_array_result(self):
        types, _ = analyze(
            "func main() { let values = [1, 2] print(len(identity(values))) }\n"
            "func identity(values) { values }"
        )
        self.assertEqual(types["identity"].result.name, "INT_ARRAY")

    def test_length_rejects_forward_result_that_is_not_an_array(self):
        for body in ("1", ""):
            with self.subTest(body=body):
                with self.assertRaises(CompileError) as raised:
                    analyze("func main() { print(len(make())) }\nfunc make() { " + body + " }")
                self.assertIn("len expects exactly one integer array", str(raised.exception))

    def test_length_cannot_be_redefined(self):
        with self.assertRaises(CompileError) as raised:
            analyze("func len(value) { value }\nfunc main() {}")
        self.assertIn("cannot redefine builtin 'len'", str(raised.exception))

    def test_indexing_infers_array_and_integer_parameters(self):
        types, _ = analyze(
            "func read_at(values, index) { values[index] }\n"
            "func main() { print(read_at([1, 2], 1)) }"
        )
        self.assertEqual([kind.name for kind in types["read_at"].parameters], ["INT_ARRAY", "INT"])

    def test_dynamic_invalid_indexes_are_left_to_runtime_checks(self):
        for index in ("0 - 1", "len(values)"):
            with self.subTest(index=index):
                types, _ = analyze(
                    "func main() { let values = [1] let index = " + index + " print(values[index]) }"
                )
                self.assertIn("main", types)

    def test_returning_locally_created_array_is_accepted(self):
        types, _ = analyze(
            "func make() { [1, 2, 3] }\n"
            "func main() { let values = make() print(values[0]) }"
        )
        self.assertEqual(types["make"].result.name, "INT_ARRAY")


class RunExitStatusTests(unittest.TestCase):
    def test_run_preserves_failure_status(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from compiler.cli import main

        for child_status, expected in ((0, 0), (7, 7), (-4, 1)):
            with self.subTest(child_status=child_status):
                with (
                    patch("sys.argv", ["kinetic", "run", "example.kn"]),
                    patch("compiler.cli.build_command", return_value=Path("example.exe")),
                    patch("compiler.cli.subprocess.run", return_value=SimpleNamespace(returncode=child_status)),
                    redirect_stdout(StringIO()),
                ):
                    self.assertEqual(main(), expected)


class DiagnosticExampleTests(unittest.TestCase):
    ERROR_CASES = {
        "immutable_reassign.kn": "cannot reassign immutable variable",
        "out_of_bounds.kn": "out of bounds",
        "missing_main.kn": "no 'main' entry point",
        "old_fn_keyword.kn": "func",
        "old_let_mut.kn": "mut name = value",
        "undefined_variable.kn": "undefined variable",
        "type_mismatch.kn": "",
        "main_parameters.kn": "cannot have parameters",
        "duplicate_parameters.kn": "duplicate parameter",
    }

    def test_error_examples_fail_with_expected_diagnostic(self):
        from pathlib import Path
        from compiler.errors import KineticError

        for name, expected in self.ERROR_CASES.items():
            with self.subTest(example=name):
                source = Path("examples/errors") / name
                text = source.read_text(encoding="utf-8")
                with self.assertRaises(KineticError) as raised:
                    analyze(text)
                if expected:
                    self.assertIn(expected, str(raised.exception))

    def test_warning_examples_emit_expected_warnings(self):
        from pathlib import Path

        unused = Path("examples/warnings/unused_variable.kn").read_text(encoding="utf-8")
        _, diagnostics = analyze(unused)
        self.assertTrue(
            any("never used" in w for w in diagnostics.render_warnings())
        )

        shadow = Path("examples/warnings/shadowing.kn").read_text(encoding="utf-8")
        _, diagnostics = analyze(shadow)
        self.assertTrue(
            any("shadows" in w for w in diagnostics.render_warnings())
        )

    def test_valid_examples_pass_frontend(self):
        from pathlib import Path

        for name in (
            "01_hello.kn", "02_logic.kn", "03_arrays.kn",
            "04_bounds_checked.kn", "05_mutability.kn",
            "06_status_handling.kn", "07_byte_processing.kn",
            "08_array_lengths.kn", "09_array_lifetimes.kn",
        ):
            with self.subTest(example=name):
                text = Path("examples", name).read_text(encoding="utf-8")
                types, _ = analyze(text)
                self.assertIn("main", types)


if __name__ == "__main__":
    unittest.main()
