from llvmlite import binding, ir

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
from .errors import CompileError
from .types import FunctionType, KType


class LLVMBackend:
    def __init__(self, program: Program, function_types: dict[str, FunctionType]):
        self.program = program
        self.function_types = function_types
        self.module = ir.Module(name="kinetic")
        self.module.triple = binding.get_default_triple()
        self.i8 = ir.IntType(8)
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)
        self.ptr = self.i8.as_pointer()
        self.array_type = ir.LiteralStructType([self.i64.as_pointer(), self.i64])
        self.functions: dict[str, ir.Function] = {}
        self.string_counter = 0

        printf_type = ir.FunctionType(self.i32, [self.ptr], var_arg=True)
        self.printf = ir.Function(self.module, printf_type, name="printf")

    def generate(self) -> str:
        self._declare_functions()
        for function in self.program.functions:
            self._emit_function(function)
        return str(self.module)

    def _llvm_type(self, kind: KType) -> ir.Type:
        if kind is KType.INT:
            return self.i64
        if kind is KType.STRING:
            return self.ptr
        if kind is KType.BOOL:
            return ir.IntType(1)
        if kind is KType.INT_ARRAY:
            return self.array_type
        if kind is KType.VOID:
            return ir.VoidType()
        raise CompileError("An unresolved type reached the LLVM backend")

    def _declare_functions(self) -> None:
        for function in self.program.functions:
            signature = self.function_types[function.name]
            if function.name == "main":
                llvm_signature = ir.FunctionType(self.i32, [])
            else:
                llvm_signature = ir.FunctionType(
                    self._llvm_type(signature.result),
                    [self._llvm_type(kind) for kind in signature.parameters],
                )
            llvm_function = ir.Function(
                self.module, llvm_signature, name=function.name
            )
            for argument, name in zip(llvm_function.args, function.parameters):
                argument.name = name
            self.functions[function.name] = llvm_function

    def _emit_function(self, function: Function) -> None:
        llvm_function = self.functions[function.name]
        builder = ir.IRBuilder(llvm_function.append_basic_block("entry"))
        environment = dict(zip(function.parameters, llvm_function.args))
        mutables: set[str] = set()

        last_value = self._emit_block(function.body, builder, environment, mutables)

        if function.name == "main":
            builder.ret(ir.Constant(self.i32, 0))
        elif isinstance(llvm_function.function_type.return_type, ir.VoidType):
            builder.ret_void()
        elif last_value is None:
            raise CompileError(f"Function {function.name!r} has no return expression")
        else:
            builder.ret(last_value)

    def _emit_block(self, block: list[Statement], builder: ir.IRBuilder, environment: dict[str, ir.Value], mutables: set[str]) -> ir.Value | None:
        last_value = None
        env = environment.copy()
        muts = mutables.copy()
        for statement in block:
            if isinstance(statement, LetStatement):
                val = self._require_value(
                    self._emit_expr(statement.value, builder, env, muts)
                )
                if statement.is_mut:
                    ptr = builder.alloca(val.type, name=statement.name)
                    builder.store(val, ptr)
                    env[statement.name] = ptr
                    muts.add(statement.name)
                else:
                    env[statement.name] = val
                    muts.discard(statement.name)
                last_value = None

            elif isinstance(statement, AssignStatement):
                val = self._require_value(self._emit_expr(statement.value, builder, env, muts))
                ptr = env[statement.name]
                builder.store(val, ptr)
                last_value = None

            elif isinstance(statement, WhileStatement):
                cond_block = builder.function.append_basic_block("while.cond")
                body_block = builder.function.append_basic_block("while.body")
                end_block = builder.function.append_basic_block("while.end")

                builder.branch(cond_block)
                builder.position_at_end(cond_block)

                condition = self._require_value(self._emit_expr(statement.condition, builder, env, muts))
                builder.cbranch(condition, body_block, end_block)

                builder.position_at_end(body_block)
                self._emit_block(statement.body, builder, env, muts)
                if not builder.block.is_terminated:
                    builder.branch(cond_block)

                builder.position_at_end(end_block)
                last_value = None

            elif isinstance(statement, IfStatement):
                last_value = self._emit_if(statement, builder, env, muts)

            elif isinstance(statement, ExpressionStatement):
                last_value = self._emit_expr(statement.expression, builder, env, muts)

        return last_value

    def _emit_if(self, statement: IfStatement, builder: ir.IRBuilder, environment: dict[str, ir.Value], mutables: set[str]) -> ir.Value | None:
        condition = self._require_value(self._emit_expr(statement.condition, builder, environment, mutables))

        then_block = builder.function.append_basic_block("then")
        merge_block = builder.function.append_basic_block("ifcont")

        if statement.else_branch is not None:
            else_block = builder.function.append_basic_block("else")
            builder.cbranch(condition, then_block, else_block)

            builder.position_at_end(else_block)
            else_val = self._emit_block(statement.else_branch, builder, environment, mutables)

            if not builder.block.is_terminated:
                builder.branch(merge_block)
            else_end_block = builder.block
        else:
            builder.cbranch(condition, then_block, merge_block)
            else_val = None
            else_end_block = None

        builder.position_at_end(then_block)
        then_val = self._emit_block(statement.then_branch, builder, environment, mutables)

        if not builder.block.is_terminated:
            builder.branch(merge_block)
        then_end_block = builder.block

        builder.position_at_end(merge_block)

        if statement.else_branch is not None and then_val is not None and else_val is not None:
            if then_val.type == else_val.type and not isinstance(then_val.type, ir.VoidType):
                phi = builder.phi(then_val.type, name="ifres")
                phi.add_incoming(then_val, then_end_block)
                phi.add_incoming(else_val, else_end_block)
                return phi
        return None

    def _emit_expr(
        self, expression: Expr, builder: ir.IRBuilder, environment: dict[str, ir.Value], mutables: set[str]
    ) -> ir.Value | None:
        if isinstance(expression, NumberExpr):
            return ir.Constant(self.i64, expression.value)
        if isinstance(expression, StringExpr):
            return self._global_string(expression.value, builder, "str")
        if isinstance(expression, NameExpr):
            if expression.name not in environment:
                raise CompileError(f"Undefined variable {expression.name!r}")
            val = environment[expression.name]
            if expression.name in mutables:
                return builder.load(val, name=expression.name + "_load")
            return val
        if isinstance(expression, ArrayExpr):
            size = ir.Constant(self.i64, len(expression.elements))
            ptr = builder.call(
                self._malloc(),
                [ir.Constant(self.i64, len(expression.elements) * 8)],
                name="array.heap",
            )
            if expression.elements:
                alloc_failed = builder.icmp_signed(
                    "==", ptr, ir.Constant(ptr.type, None), name="alloc.failed"
                )
                ok_block = builder.function.append_basic_block("alloc.ok")
                fail_block = builder.function.append_basic_block("alloc.fail")
                builder.cbranch(alloc_failed, fail_block, ok_block)
                builder.position_at_end(fail_block)
                self._emit_trap(builder)
                builder.position_at_end(ok_block)
            for i, element in enumerate(expression.elements):
                val = self._require_value(self._emit_expr(element, builder, environment, mutables))
                idx = ir.Constant(self.i32, i)
                elem_ptr = builder.gep(ptr, [idx], name="elem_ptr")
                builder.store(val, elem_ptr)
            array = builder.insert_value(
                ir.Constant(self.array_type, ir.Undefined), ptr, 0, name="array.data"
            )
            return builder.insert_value(array, size, 1, name="array.value")
        if isinstance(expression, IndexExpr):
            collection = self._require_value(self._emit_expr(expression.collection, builder, environment, mutables))
            index = self._require_value(self._emit_expr(expression.index, builder, environment, mutables))
            if collection.type == self.ptr:
                length = builder.call(self._strlen(), [collection], name="text.length")
                self._emit_index_guard(builder, index, length)
                elem_ptr = builder.gep(collection, [index], name="elem_ptr")
                byte = builder.load(elem_ptr, name="elem.byte")
                return builder.zext(byte, self.i64, name="elem")
            data = builder.extract_value(collection, 0, name="array.ptr")
            length = builder.extract_value(collection, 1, name="array.length")
            self._emit_index_guard(builder, index, length)
            elem_ptr = builder.gep(data, [index], name="elem_ptr")
            return builder.load(elem_ptr, name="elem")
        if isinstance(expression, BinaryExpr):
            return self._emit_binary(expression, builder, environment, mutables)
        if isinstance(expression, CallExpr):
            return self._emit_call(expression, builder, environment, mutables)
        raise AssertionError(f"Unhandled expression: {expression!r}")

    def _emit_index_guard(
        self, builder: ir.IRBuilder, index: ir.Value, length: ir.Value
    ) -> None:
        nonnegative = builder.icmp_signed(
            ">=", index, ir.Constant(self.i64, 0), name="index.nonnegative"
        )
        below_length = builder.icmp_signed("<", index, length, name="index.below_length")
        valid = builder.and_(nonnegative, below_length, name="index.valid")
        self._emit_bounds_guard(builder, valid)

    def _emit_bounds_guard(self, builder: ir.IRBuilder, valid: ir.Value) -> None:
        valid_block = builder.function.append_basic_block("bounds.ok")
        invalid_block = builder.function.append_basic_block("bounds.fail")
        builder.cbranch(valid, valid_block, invalid_block)
        builder.position_at_end(invalid_block)
        self._emit_trap(builder)
        builder.position_at_end(valid_block)

    def _strlen(self) -> ir.Function:
        function = self.module.globals.get("strlen")
        if function is None:
            function = ir.Function(
                self.module, ir.FunctionType(self.i64, [self.ptr]), name="strlen"
            )
        return function

    def _strcmp(self) -> ir.Function:
        function = self.module.globals.get("strcmp")
        if function is None:
            function = ir.Function(
                self.module,
                ir.FunctionType(self.i32, [self.ptr, self.ptr]),
                name="strcmp",
            )
        return function

    def _memcpy(self) -> ir.Function:
        function = self.module.globals.get("memcpy")
        if function is None:
            function = ir.Function(
                self.module,
                ir.FunctionType(self.ptr, [self.ptr, self.ptr, self.i64]),
                name="memcpy",
            )
        return function

    def _emit_binary(
        self,
        expression: BinaryExpr,
        builder: ir.IRBuilder,
        environment: dict[str, ir.Value],
        mutables: set[str],
    ) -> ir.Value:
        left = self._require_value(
            self._emit_expr(expression.left, builder, environment, mutables)
        )
        right = self._require_value(
            self._emit_expr(expression.right, builder, environment, mutables)
        )
        if left.type == self.ptr and right.type == self.ptr:
            if expression.operator == "+":
                return self._emit_concat(left, right, builder)
            if expression.operator in ("==", "<", ">"):
                comparison = builder.call(
                    self._strcmp(), [left, right], name="text.compare"
                )
                ops = {"==": "==", "<": "<", ">": ">"}
                return builder.icmp_signed(
                    ops[expression.operator],
                    comparison,
                    ir.Constant(self.i32, 0),
                    name="cmp",
                )
            raise CompileError(
                f"operator {expression.operator!r} is not defined for strings"
            )
        if expression.operator in ("==", "<", ">"):
            ops = {"==": "==", "<": "<", ">": ">"}
            return builder.icmp_signed(ops[expression.operator], left, right, name="cmp")

        operations = {
            "+": builder.add,
            "-": builder.sub,
            "*": builder.mul,
            "/": builder.sdiv,
        }
        return operations[expression.operator](left, right, name="binop")

    def _emit_string_alloc(
        self, builder: ir.IRBuilder, size: ir.Value, prefix: str
    ) -> ir.Value:
        raw = builder.call(self._malloc(), [size], name=prefix + ".raw")
        alloc_failed = builder.icmp_signed(
            "==", raw, ir.Constant(raw.type, None), name="alloc.failed"
        )
        ok_block = builder.function.append_basic_block("alloc.ok")
        fail_block = builder.function.append_basic_block("alloc.fail")
        builder.cbranch(alloc_failed, fail_block, ok_block)
        builder.position_at_end(fail_block)
        self._emit_trap(builder)
        builder.position_at_end(ok_block)
        return builder.bitcast(raw, self.ptr, name=prefix + ".buffer")

    def _emit_concat(
        self, left: ir.Value, right: ir.Value, builder: ir.IRBuilder
    ) -> ir.Value:
        left_length = builder.call(self._strlen(), [left], name="text.length")
        right_length = builder.call(self._strlen(), [right], name="text.length")
        count = builder.add(left_length, right_length, name="concat.count")
        size = builder.add(count, ir.Constant(self.i64, 1), name="concat.size")
        buffer = self._emit_string_alloc(builder, size, "concat")
        builder.call(self._memcpy(), [buffer, left, left_length])
        tail = builder.gep(buffer, [left_length], name="concat.tail")
        tail_size = builder.add(
            right_length, ir.Constant(self.i64, 1), name="concat.tail_size"
        )
        builder.call(self._memcpy(), [tail, right, tail_size])
        return buffer

    def _emit_slice(
        self,
        text: ir.Value,
        start: ir.Value,
        end: ir.Value,
        builder: ir.IRBuilder,
    ) -> ir.Value:
        length = builder.call(self._strlen(), [text], name="text.length")
        zero = ir.Constant(self.i64, 0)
        start_ok = builder.icmp_signed(">=", start, zero, name="slice.start_ok")
        order_ok = builder.icmp_signed(">=", end, start, name="slice.order_ok")
        within_ok = builder.icmp_signed("<=", end, length, name="slice.within_ok")
        valid = builder.and_(start_ok, order_ok, name="slice.ordered")
        valid = builder.and_(valid, within_ok, name="slice.valid")
        self._emit_bounds_guard(builder, valid)
        count = builder.sub(end, start, name="slice.count")
        size = builder.add(count, ir.Constant(self.i64, 1), name="slice.size")
        buffer = self._emit_string_alloc(builder, size, "slice")
        source = builder.gep(text, [start], name="slice.source")
        builder.call(self._memcpy(), [buffer, source, count])
        nul_ptr = builder.gep(buffer, [count], name="slice.nul")
        builder.store(ir.Constant(self.i8, 0), nul_ptr)
        return buffer

    def _emit_call(
        self,
        expression: CallExpr,
        builder: ir.IRBuilder,
        environment: dict[str, ir.Value],
        mutables: set[str],
    ) -> ir.Value | None:
        arguments = [
            self._require_value(self._emit_expr(argument, builder, environment, mutables))
            for argument in expression.arguments
        ]
        if expression.callee == "len":
            argument = arguments[0]
            if argument.type == self.ptr:
                return builder.call(self._strlen(), [argument], name="text.length")
            return builder.extract_value(argument, 1, name="array.length")
        if expression.callee == "slice":
            return self._emit_slice(arguments[0], arguments[1], arguments[2], builder)
        if expression.callee == "print":
            self._emit_print(arguments[0], builder)
            return None
        return builder.call(
            self.functions[expression.callee], arguments, name="call"
        )

    def _emit_print(self, value: ir.Value, builder: ir.IRBuilder) -> None:
        if value.type == self.i64:
            format_string = self._global_string("%lld\n", builder, "fmt.int")
        elif value.type == self.ptr:
            format_string = self._global_string("%s\n", builder, "fmt.str")
        else:
            raise CompileError(f"print cannot emit LLVM type {value.type}")
        builder.call(self.printf, [format_string, value])

    def _emit_trap(self, builder: ir.IRBuilder) -> None:
        trap = self.module.globals.get("llvm.trap")
        if trap is None:
            trap = ir.Function(
                self.module, ir.FunctionType(ir.VoidType(), []), name="llvm.trap"
            )
        builder.call(trap, [])
        builder.unreachable()

    def _malloc(self) -> ir.Function:
        malloc = self.module.globals.get("malloc")
        if malloc is None:
            malloc = ir.Function(
                self.module,
                ir.FunctionType(self.i64.as_pointer(), [self.i64]),
                name="malloc",
            )
        return malloc

    @staticmethod
    def _require_value(value: ir.Value | None) -> ir.Value:
        if value is None:
            raise CompileError("A void expression was used as a value")
        return value

    def _global_string(
        self, text: str, builder: ir.IRBuilder, prefix: str
    ) -> ir.Value:
        encoded = text.encode("utf-8") + b"\0"
        array_type = ir.ArrayType(self.i8, len(encoded))
        name = f".{prefix}.{self.string_counter}"
        self.string_counter += 1
        global_value = ir.GlobalVariable(self.module, array_type, name=name)
        global_value.linkage = "private"
        global_value.global_constant = True
        global_value.initializer = ir.Constant(array_type, bytearray(encoded))
        zero = ir.Constant(self.i32, 0)
        return builder.gep(global_value, [zero, zero], inbounds=True, name="strptr")
