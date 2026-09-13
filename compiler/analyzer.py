from .ast import (
    ArrayExpr,
    AssignStatement,
    BinaryExpr,
    CallExpr,
    Expr,
    ExpressionStatement,
    Function,
    IfStatement,
    IndexExpr,
    LetStatement,
    NameExpr,
    NumberExpr,
    Program,
    Statement,
    StringExpr,
    WhileStatement,
)
from .diagnostics import Diagnostics
from .errors import CompileError
from .types import FunctionType, KType


class TypeAnalyzer:
    def __init__(self, program: Program, diagnostics: Diagnostics | None = None):
        self.program = program
        self.diagnostics = (
            diagnostics if diagnostics is not None else Diagnostics()
        )
        function_names = {function.name for function in program.functions}
        if len(function_names) != len(program.functions):
            raise CompileError("duplicate function definition")
        if "main" not in function_names:
            location = program.functions[0].location if program.functions else None
            raise CompileError(
                "program has no 'main' entry point",
                location.line if location else None,
                location.column if location else None,
            )

        for function in program.functions:
            if function.name in ("len", "slice"):
                location = function.location
                raise CompileError(
                    f"cannot redefine builtin {function.name!r}",
                    location.line if location else None,
                    location.column if location else None,
                )
            seen_parameters: set[str] = set()
            for parameter in function.parameters:
                if parameter in seen_parameters:
                    location = function.location
                    raise CompileError(
                        f"duplicate parameter {parameter!r} in function "
                        f"{function.name!r}",
                        location.line if location else None,
                        location.column if location else None,
                    )
                seen_parameters.add(parameter)

        main = next(function for function in program.functions if function.name == "main")
        if main.parameters:
            location = main.location
            raise CompileError(
                "'main' entry point cannot have parameters",
                location.line if location else None,
                location.column if location else None,
            )

        self.types = {
            function.name: FunctionType(
                [KType.UNKNOWN] * len(function.parameters), KType.UNKNOWN
            )
            for function in program.functions
        }
        self._array_lengths: dict[str, int] = {}
        self._binding_ids: dict[str, int | None] = {}
        self._final_validation = False

    def analyze(self) -> dict[str, FunctionType]:
        for _ in range(max(2, len(self.program.functions) + 1)):
            changed = False
            for function in self.program.functions:
                changed |= self._analyze_function(function)
            if not changed:
                break

        for signature in self.types.values():
            if signature.result is KType.UNKNOWN:
                signature.result = KType.VOID

        self._final_validation = True
        for function in self.program.functions:
            self._analyze_function(function)

        for name, signature in self.types.items():
            if any(kind is KType.UNKNOWN for kind in signature.parameters):
                function = next(
                    item for item in self.program.functions if item.name == name
                )
                location = function.location
                raise CompileError(
                    f"could not infer all parameter types for {name!r}",
                    location.line if location else None,
                    location.column if location else None,
                )

        return self.types

    @staticmethod
    def _location_of(expression: Expr | Statement) -> tuple[int | None, int | None]:
        location = expression.location
        if location is None:
            return None, None
        return location.line, location.column

    @staticmethod
    def _unify(old: KType, new: KType, context: str) -> KType:
        if new is KType.UNKNOWN:
            return old
        if old is KType.UNKNOWN:
            return new
        if old is not new:
            raise CompileError(f"type mismatch in {context}: {old.name} vs {new.name}")
        return old

    def _restore_array_lengths(self, lengths: dict[str, int]) -> None:
        self._array_lengths.clear()
        self._array_lengths.update(lengths)

    def _merge_array_lengths(self, paths: list[dict[str, int]]) -> None:
        if not paths:
            self._array_lengths.clear()
            return

        common_names = set(paths[0])
        for path in paths[1:]:
            common_names.intersection_update(path)

        merged = {
            name: paths[0][name]
            for name in common_names
            if all(path[name] == paths[0][name] for path in paths[1:])
        }
        self._restore_array_lengths(merged)

    def _analyze_function(self, function: Function) -> bool:
        signature = self.types[function.name]

        environment = dict(zip(function.parameters, signature.parameters))
        self._binding_ids = {parameter: None for parameter in function.parameters}
        self._array_lengths.clear()

        mutables: set[str] = set()
        used: set[int] = set()

        last_type = self._analyze_block(
            function.body, environment, mutables, used
        )

        for statement in self._declared_bindings(function.body):
            if id(statement) not in used:
                self.diagnostics.warn(
                    f"variable {statement.name!r} is never used",
                    statement.location,
                )

        changed = False

        for index, parameter in enumerate(function.parameters):
            inferred = environment[parameter]
            unified = self._unify(
                signature.parameters[index], inferred, f"parameter {parameter!r}"
            )
            if unified is not signature.parameters[index]:
                signature.parameters[index] = unified
                changed = True

        expected_result = KType.INT if function.name == "main" else last_type

        if (
            self._final_validation
            and signature.result is KType.VOID
            and expected_result not in (KType.VOID, KType.UNKNOWN)
        ):
            signature.result = expected_result
            changed = True
        else:
            unified_result = self._unify(
                signature.result, expected_result, f"return value of {function.name!r}"
            )
            if unified_result is not signature.result:
                signature.result = unified_result
                changed = True

        return changed

    def _declared_bindings(self, block: list[Statement]):
        for statement in block:
            if isinstance(statement, LetStatement):
                yield statement
            if isinstance(statement, IfStatement):
                yield from self._declared_bindings(statement.then_branch)
                if statement.else_branch is not None:
                    yield from self._declared_bindings(statement.else_branch)
            if isinstance(statement, WhileStatement):
                yield from self._declared_bindings(statement.body)

    def _analyze_block(
        self,
        block: list[Statement],
        environment: dict[str, KType],
        mutables: set[str],
        used: set[int],
    ) -> KType:
        last_type = KType.VOID
        declared_here: set[str] = set()
        prior_types: dict[str, tuple[bool, KType | None]] = {}
        prior_mutability: dict[str, bool] = {}
        prior_lengths: dict[str, tuple[bool, int | None]] = {}
        prior_binding_ids: dict[str, tuple[bool, int | None]] = {}

        for statement in block:
            if isinstance(statement, LetStatement):
                if statement.name in environment:
                    self.diagnostics.warn(
                        f"declaration of {statement.name!r} shadows an "
                        "existing binding",
                        statement.location,
                    )
                if statement.name not in declared_here:
                    declared_here.add(statement.name)
                    prior_types[statement.name] = (
                        statement.name in environment,
                        environment.get(statement.name),
                    )
                    prior_mutability[statement.name] = statement.name in mutables
                    prior_lengths[statement.name] = (
                        statement.name in self._array_lengths,
                        self._array_lengths.get(statement.name),
                    )
                    prior_binding_ids[statement.name] = (
                        statement.name in self._binding_ids,
                        self._binding_ids.get(statement.name),
                    )

                value_type = self._expr_type(statement.value, environment, used)
                if value_type is KType.VOID:
                    line, column = self._location_of(statement)
                    raise CompileError(
                        "cannot bind a void expression", line, column
                    )
                environment[statement.name] = value_type
                self._binding_ids[statement.name] = id(statement)
                if statement.is_mut:
                    mutables.add(statement.name)
                else:
                    mutables.discard(statement.name)
                known_length = self._known_array_length(statement.value)
                if known_length is not None:
                    self._array_lengths[statement.name] = known_length
                else:
                    self._array_lengths.pop(statement.name, None)
                last_type = KType.VOID

            elif isinstance(statement, AssignStatement):
                line, column = self._location_of(statement)
                if statement.name not in environment:
                    raise CompileError(
                        f"undefined variable {statement.name!r}", line, column
                    )
                if statement.name not in mutables:
                    raise CompileError(
                        f"cannot reassign immutable variable {statement.name!r}",
                        line,
                        column,
                    )
                binding_id = self._binding_ids.get(statement.name)
                if binding_id is not None:
                    used.add(binding_id)
                value_type = self._expr_type(statement.value, environment, used)
                self._unify(
                    environment[statement.name],
                    value_type,
                    f"assignment to {statement.name!r}",
                )
                known_length = self._known_array_length(statement.value)
                if known_length is not None:
                    self._array_lengths[statement.name] = known_length
                else:
                    self._array_lengths.pop(statement.name, None)
                last_type = KType.VOID

            elif isinstance(statement, WhileStatement):
                cond_type = self._expr_type(statement.condition, environment, used)
                self._constrain_name(statement.condition, KType.BOOL, environment)
                if cond_type not in (KType.BOOL, KType.UNKNOWN):
                    line, column = self._location_of(statement.condition)
                    raise CompileError(
                        "while condition must be a boolean", line, column
                    )
                before_lengths = dict(self._array_lengths)
                self._analyze_block(statement.body, environment, mutables, used)
                after_lengths = dict(self._array_lengths)
                self._merge_array_lengths([before_lengths, after_lengths])
                last_type = KType.VOID

            elif isinstance(statement, IfStatement):
                cond_type = self._expr_type(statement.condition, environment, used)
                self._constrain_name(statement.condition, KType.BOOL, environment)
                if cond_type not in (KType.BOOL, KType.UNKNOWN):
                    line, column = self._location_of(statement.condition)
                    raise CompileError(
                        "if condition must be a boolean", line, column
                    )

                before_lengths = dict(self._array_lengths)
                then_type = self._analyze_block(
                    statement.then_branch, environment, mutables, used
                )
                then_lengths = dict(self._array_lengths)
                self._restore_array_lengths(before_lengths)

                if statement.else_branch is not None:
                    else_type = self._analyze_block(
                        statement.else_branch, environment, mutables, used
                    )
                    else_lengths = dict(self._array_lengths)
                    self._merge_array_lengths([then_lengths, else_lengths])
                    last_type = self._unify(then_type, else_type, "if/else branches")
                else:
                    self._merge_array_lengths([before_lengths, then_lengths])
                    last_type = KType.VOID

            elif isinstance(statement, ExpressionStatement):
                last_type = self._expr_type(statement.expression, environment, used)

        for name in declared_here:
            had_type, prior_type = prior_types[name]
            if had_type:
                assert prior_type is not None
                environment[name] = prior_type
            else:
                environment.pop(name, None)

            if prior_mutability[name]:
                mutables.add(name)
            else:
                mutables.discard(name)

            had_length, prior_length = prior_lengths[name]
            if had_length:
                assert prior_length is not None
                self._array_lengths[name] = prior_length
            else:
                self._array_lengths.pop(name, None)

            had_binding, prior_binding = prior_binding_ids[name]
            if had_binding:
                self._binding_ids[name] = prior_binding
            else:
                self._binding_ids.pop(name, None)

        return last_type

    def _expr_type(
        self, expression: Expr, environment: dict[str, KType], used: set[int]
    ) -> KType:
        if isinstance(expression, NumberExpr):
            return KType.INT
        if isinstance(expression, StringExpr):
            return KType.STRING
        if isinstance(expression, NameExpr):
            if expression.name not in environment:
                line, column = self._location_of(expression)
                raise CompileError(
                    f"undefined variable {expression.name!r}", line, column
                )
            binding_id = self._binding_ids.get(expression.name)
            if binding_id is not None:
                used.add(binding_id)
            return environment[expression.name]
        if isinstance(expression, ArrayExpr):
            for element in expression.elements:
                elem_type = self._expr_type(element, environment, used)
                self._unify(elem_type, KType.INT, "array element")
            return KType.INT_ARRAY
        if isinstance(expression, IndexExpr):
            collection_type = self._expr_type(
                expression.collection, environment, used
            )
            index_type = self._expr_type(expression.index, environment, used)
            self._unify(index_type, KType.INT, "array index")
            self._constrain_name(expression.index, KType.INT, environment)
            if collection_type is KType.UNKNOWN and not self._final_validation:
                return KType.INT
            if collection_type is KType.UNKNOWN:
                self._constrain_name(
                    expression.collection, KType.INT_ARRAY, environment
                )
                collection_type = KType.INT_ARRAY
            if collection_type not in (KType.INT_ARRAY, KType.STRING):
                line, column = self._location_of(expression)
                raise CompileError(
                    "indexing expects an integer array or string", line, column
                )
            if (
                collection_type is KType.INT_ARRAY
                and isinstance(expression.collection, NameExpr)
                and isinstance(expression.index, NumberExpr)
            ):
                self._check_constant_bounds(expression, environment)
            return KType.INT
        if isinstance(expression, BinaryExpr):
            return self._binary_type(expression, environment, used)
        if isinstance(expression, CallExpr):
            return self._call_type(expression, environment, used)
        raise AssertionError(f"Unhandled expression: {expression!r}")

    def _known_array_length(self, expression: Expr) -> int | None:
        if isinstance(expression, ArrayExpr):
            return len(expression.elements)
        if isinstance(expression, NameExpr):
            return self._array_lengths.get(expression.name)
        return None

    def _check_constant_bounds(
        self, expression: IndexExpr, environment: dict[str, KType]
    ) -> None:
        index = expression.index
        if not isinstance(index, NumberExpr) or index.value < 0:
            return
        lengths = self._array_lengths.get(expression.collection.name, None)
        if lengths is not None and index.value >= lengths:
            line, column = self._location_of(expression)
            raise CompileError(
                f"index {index.value} is out of bounds for array "
                f"{expression.collection.name!r} of length {lengths}",
                line,
                column,
            )

    def _binary_type(
        self, expression: BinaryExpr, environment: dict[str, KType], used: set[int]
    ) -> KType:
        left = self._expr_type(expression.left, environment, used)
        right = self._expr_type(expression.right, environment, used)
        if KType.STRING in (left, right):
            return self._string_binary_type(expression, left, right, environment)
        if (
            left is KType.UNKNOWN
            and right is KType.UNKNOWN
            and not self._final_validation
        ):
            if expression.operator in ("==", "<", ">"):
                return KType.BOOL
            return KType.UNKNOWN
        if left not in (KType.INT, KType.UNKNOWN) or right not in (
            KType.INT,
            KType.UNKNOWN,
        ):
            line, column = self._location_of(expression)
            raise CompileError(
                f"operator {expression.operator!r} requires integers",
                line,
                column,
            )
        self._constrain_name(expression.left, KType.INT, environment)
        self._constrain_name(expression.right, KType.INT, environment)
        if expression.operator in ("==", "<", ">"):
            return KType.BOOL
        return KType.INT

    def _string_binary_type(
        self,
        expression: BinaryExpr,
        left: KType,
        right: KType,
        environment: dict[str, KType],
    ) -> KType:
        line, column = self._location_of(expression)
        for operand_type, operand in (
            (left, expression.left),
            (right, expression.right),
        ):
            if operand_type is KType.UNKNOWN:
                self._constrain_name(operand, KType.STRING, environment)
            elif operand_type is not KType.STRING:
                raise CompileError(
                    f"operator {expression.operator!r} requires matching "
                    "operand types",
                    line,
                    column,
                )
        if expression.operator in ("==", "<", ">"):
            return KType.BOOL
        if expression.operator == "+":
            return KType.STRING
        raise CompileError(
            f"operator {expression.operator!r} is not defined for strings",
            line,
            column,
        )

    def _call_type(
        self, expression: CallExpr, environment: dict[str, KType], used: set[int]
    ) -> KType:
        argument_types = [
            self._expr_type(argument, environment, used)
            for argument in expression.arguments
        ]
        if expression.callee == "len":
            line, column = self._location_of(expression)
            if len(argument_types) != 1:
                raise CompileError(
                    "len expects exactly one integer array or string", line, column
                )
            argument_type = argument_types[0]
            argument = expression.arguments[0]
            if argument_type is KType.UNKNOWN:
                if not self._final_validation:
                    return KType.INT
                if isinstance(argument, NameExpr):
                    self._constrain_name(argument, KType.INT_ARRAY, environment)
                    argument_type = KType.INT_ARRAY
                else:
                    raise CompileError(
                        "could not infer array argument to len", line, column
                    )
            if argument_type not in (KType.INT_ARRAY, KType.STRING):
                raise CompileError(
                    "len expects exactly one integer array or string", line, column
                )
            return KType.INT
        if expression.callee == "slice":
            line, column = self._location_of(expression)
            if len(argument_types) != 3:
                raise CompileError(
                    "slice expects a string, a start index, and an end index",
                    line,
                    column,
                )
            contexts = ("slice text", "slice start", "slice end")
            expected = (KType.STRING, KType.INT, KType.INT)
            for argument, argument_type, context, wanted in zip(
                expression.arguments, argument_types, contexts, expected
            ):
                self._unify(argument_type, wanted, context)
                self._constrain_name(argument, wanted, environment)
            return KType.STRING
        if expression.callee == "print":
            printable_types = (KType.INT, KType.STRING)
            if not self._final_validation:
                printable_types += (KType.UNKNOWN,)
            if len(argument_types) != 1 or argument_types[0] not in printable_types:
                line, column = self._location_of(expression)
                raise CompileError(
                    "print expects one integer or string argument", line, column
                )
            return KType.VOID
        if expression.callee not in self.types:
            line, column = self._location_of(expression)
            raise CompileError(
                f"undefined function {expression.callee!r}", line, column
            )

        signature = self.types[expression.callee]
        if len(argument_types) != len(signature.parameters):
            line, column = self._location_of(expression)
            raise CompileError(
                f"function {expression.callee!r} expects "
                f"{len(signature.parameters)} arguments",
                line,
                column,
            )
        for index, argument_type in enumerate(argument_types):
            signature.parameters[index] = self._unify(
                signature.parameters[index],
                argument_type,
                f"call to {expression.callee!r}",
            )
        return signature.result

    def _constrain_name(
        self, expression: Expr, required: KType, environment: dict[str, KType]
    ) -> None:
        if isinstance(expression, NameExpr):
            environment[expression.name] = self._unify(
                environment[expression.name], required, expression.name
            )
