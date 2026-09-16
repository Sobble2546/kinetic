from dataclasses import dataclass, field

from .diagnostics import SourceLocation


class Expr:
    location: SourceLocation | None


@dataclass
class NumberExpr(Expr):
    location: SourceLocation | None = None
    value: int = 0


@dataclass
class StringExpr(Expr):
    location: SourceLocation | None = None
    value: str = ""


@dataclass
class NameExpr(Expr):
    location: SourceLocation | None = None
    name: str = ""


@dataclass
class BinaryExpr(Expr):
    location: SourceLocation | None = None
    operator: str = ""
    left: Expr | None = None
    right: Expr | None = None


@dataclass
class CallExpr(Expr):
    location: SourceLocation | None = None
    callee: str = ""
    arguments: list[Expr] = field(default_factory=list)


@dataclass
class ArrayExpr(Expr):
    location: SourceLocation | None = None
    elements: list[Expr] = field(default_factory=list)


@dataclass
class IndexExpr(Expr):
    location: SourceLocation | None = None
    collection: Expr | None = None
    index: Expr | None = None


class Statement:
    location: SourceLocation | None


@dataclass
class LetStatement(Statement):
    location: SourceLocation | None = None
    name: str = ""
    value: Expr | None = None
    is_mut: bool = False


@dataclass
class AssignStatement(Statement):
    location: SourceLocation | None = None
    name: str = ""
    value: Expr | None = None


@dataclass
class IndexAssignStatement(Statement):
    location: SourceLocation | None = None
    collection: Expr | None = None
    index: Expr | None = None
    value: Expr | None = None


@dataclass
class ExpressionStatement(Statement):
    location: SourceLocation | None = None
    expression: Expr | None = None


@dataclass
class IfStatement(Statement):
    location: SourceLocation | None = None
    condition: Expr | None = None
    then_branch: list[Statement] = field(default_factory=list)
    else_branch: list[Statement] | None = None


@dataclass
class WhileStatement(Statement):
    location: SourceLocation | None = None
    condition: Expr | None = None
    body: list[Statement] = field(default_factory=list)


@dataclass
class Function:
    name: str
    parameters: list[str]
    body: list[Statement]
    location: SourceLocation | None = None


@dataclass
class Program:
    functions: list[Function]
