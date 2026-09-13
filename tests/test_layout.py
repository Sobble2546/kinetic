import ast
from pathlib import Path
import re
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "compiler"
SOURCE_DIRECTORIES = ("compiler", "tools", "tests")
COMPILER_MODULES = (
    "analyzer", "ast", "backend", "cli", "compiler",
    "errors", "lexer", "parser", "tokens", "types",
)


def python_sources() -> list[Path]:
    files = [ROOT / "kinetic.py"]
    for directory in SOURCE_DIRECTORIES:
        files.extend(sorted((ROOT / directory).rglob("*.py")))
    return files


class RepositoryLayoutTests(unittest.TestCase):
    def test_repository_sections_exist(self):
        for directory in ("compiler", "docs", "examples", "tools", "tests"):
            with self.subTest(directory=directory):
                self.assertTrue((ROOT / directory).is_dir())

    def test_compiler_package_is_flat(self):
        for module in COMPILER_MODULES:
            with self.subTest(module=module):
                self.assertTrue((PACKAGE / f"{module}.py").is_file())
        self.assertTrue((PACKAGE / "__init__.py").is_file())
        self.assertTrue((PACKAGE / "__main__.py").is_file())
        self.assertFalse((ROOT / "kinetic").exists())
        for path in PACKAGE.rglob("*.py"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(path.parent, PACKAGE)

    def test_sample_programs_live_in_examples(self):
        self.assertEqual(list(ROOT.glob("*.kn")), [])
        for name in (
            "01_hello.kn", "02_logic.kn", "03_arrays.kn",
            "04_bounds_checked.kn", "05_mutability.kn",
            "06_status_handling.kn", "07_byte_processing.kn",
            "08_array_lengths.kn", "09_array_lifetimes.kn",
        ):
            with self.subTest(example=name):
                self.assertTrue((ROOT / "examples" / name).is_file())
        for name in (
            "immutable_reassign.kn", "out_of_bounds.kn", "missing_main.kn",
            "old_fn_keyword.kn", "old_let_mut.kn", "undefined_variable.kn",
            "type_mismatch.kn", "main_parameters.kn",
            "duplicate_parameters.kn",
            "len_type.kn", "len_arity.kn",
        ):
            with self.subTest(error_example=name):
                self.assertTrue((ROOT / "examples" / "errors" / name).is_file())
        for name in ("unused_variable.kn", "shadowing.kn"):
            with self.subTest(warning_example=name):
                self.assertTrue((ROOT / "examples" / "warnings" / name).is_file())
        for name in ("out_of_bounds.kn", "negative_index.kn"):
            with self.subTest(runtime_example=name):
                self.assertTrue((ROOT / "examples" / "runtime_errors" / name).is_file())

    def test_python_sources_parse(self):
        for path in python_sources():
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_token_kind_references_exist(self):
        tree = ast.parse((PACKAGE / "tokens.py").read_text(encoding="utf-8"))
        token_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "TokenKind"
        )
        kinds = {
            target.id
            for node in token_class.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)
        }
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "TokenKind"
                ):
                    with self.subTest(path=path.name, line=node.lineno, token=node.attr):
                        self.assertIn(node.attr, kinds)

    def test_declaration_keyword_mapping(self):
        tree = ast.parse((PACKAGE / "lexer.py").read_text(encoding="utf-8"))
        keywords = next(
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_keywords"
                for target in node.targets
            )
        )
        self.assertIsInstance(keywords, ast.Dict)
        mapping = {
            ast.literal_eval(key): value.attr
            for key, value in zip(keywords.keys, keywords.values)
        }
        self.assertEqual(mapping, {
            "func": "FUNC", "let": "LET", "mut": "MUT",
            "while": "WHILE", "if": "IF", "else": "ELSE",
        })

    def test_hello_world_is_published_in_readme(self):
        program = (ROOT / "examples" / "01_hello.kn").read_text(encoding="utf-8").strip()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"```text\n{program}\n```", readme)
        self.assertIn('print("Hello World!")', program)
        self.assertTrue(program.startswith("func main() {"))

    def test_examples_and_guide_use_current_declarations(self):
        paths = sorted((ROOT / "examples").glob("*.kn"))
        paths.append(ROOT / "docs" / "syntax_guide.md")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotRegex(text, r"(?m)^\s*fn\s+\w+\s*\(")
                self.assertNotRegex(text, r"\blet\s+mut\b")

    def test_diagnostic_examples_are_excluded_from_old_syntax_check(self):
        error_dir = ROOT / "examples" / "errors"
        self.assertIn("fn main()", (error_dir / "old_fn_keyword.kn").read_text(encoding="utf-8"))
        self.assertIn("let mut", (error_dir / "old_let_mut.kn").read_text(encoding="utf-8"))

    def test_ci_uses_shared_static_checker(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        commands = re.findall(r"^\s+run:\s*([^\n]+)$", workflow, re.MULTILINE)
        self.assertIn("python -B tools/check.py", commands)
        actions = re.findall(r"^\s+uses:\s*(\S+)", workflow, re.MULTILINE)
        for action in actions:
            with self.subTest(action=action):
                self.assertRegex(action, r"^actions/(checkout|setup-python)@[0-9a-f]{40}$")

    def test_compiler_import_targets_exist(self):
        for path in python_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        with self.subTest(path=path.relative_to(ROOT), line=node.lineno):
                            self.assertEqual(path.parent, PACKAGE)
                            self.assertEqual(node.level, 1)
                        if node.module:
                            modules.append(f"compiler.{node.module}")
                        else:
                            modules.extend(f"compiler.{alias.name}" for alias in node.names)
                    elif node.module:
                        modules.append(node.module)
                elif isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                for module in modules:
                    with self.subTest(path=path.relative_to(ROOT), module=module):
                        self.assertFalse(module == "kinetic" or module.startswith("kinetic."))
                    if module != "compiler" and not module.startswith("compiler."):
                        continue
                    target = PACKAGE.joinpath(*module.split(".")[1:])
                    with self.subTest(path=path.relative_to(ROOT), module=module):
                        self.assertTrue(
                            target.with_suffix(".py").is_file()
                            or (target / "__init__.py").is_file(),
                            f"Missing source for {module}",
                        )

    def test_public_api_is_exported(self):
        tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
        exports = [
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
        ]
        self.assertEqual(len(exports), 1)
        self.assertIn("compile_source", exports[0])
        self.assertTrue(any(
            isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
            for node in tree.body
        ))

    def test_launchers_delegate_to_cli(self):
        entrypoints = (
            (ROOT / "kinetic.py", "compiler.cli", 0),
            (PACKAGE / "__main__.py", "cli", 1),
        )
        for path, module, level in entrypoints:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(any(
                    isinstance(node, ast.ImportFrom)
                    and node.module == module
                    and node.level == level
                    and any(alias.name == "main" for alias in node.names)
                    for node in tree.body
                ))
                self.assertTrue(any(
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "main"
                    for node in ast.walk(tree)
                ))

    def test_claude_guidance_imports_shared_rules(self):
        self.assertTrue((ROOT / "AGENTS.md").is_file())
        self.assertTrue((ROOT / "ROADMAP.md").is_file())
        guidance = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("@AGENTS.md", guidance.splitlines())

    def test_local_documentation_links_exist(self):
        documents = sorted(ROOT.glob("*.md"))
        for directory in (*SOURCE_DIRECTORIES, "docs", "examples"):
            documents.extend(sorted((ROOT / directory).rglob("*.md")))
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith(("#", "mailto:")):
                    continue
                target = target.split("#", 1)[0]
                target = re.sub(r":\d+(?::\d+)?$", "", target)
                with self.subTest(document=document.relative_to(ROOT), target=target):
                    self.assertTrue(
                        (document.parent / unquote(target)).exists(),
                        f"Broken local link: {target}",
                    )


if __name__ == "__main__":
    unittest.main()
