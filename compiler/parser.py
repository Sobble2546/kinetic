from .ast import (
    ArrayExpr,
    AssignStatement,
    BinaryExpr,
    CallExpr,
    Expr,
    ExpressionStatement,
    Function,
    IfStatement,
    IndexAssignStatement,
    IndexExpr,
    LetStatement,
    NameExpr,
    NumberExpr,
    Program,
    Statement,
    StringExpr,
    WhileStatement,
)
from .diagnostics import SourceLocation
from .errors import ParseError
from .tokens import Token, TokenKind


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def parse(self) -> Program:
        functions: list[Function] = []
        while self.current.kind is not TokenKind.EOF:
            functions.append(self._parse_function())
        return Program(functions)

    def _location(self, token: Token | None = None) -> SourceLocation:
        current = token if token is not None else self.current
        return SourceLocation(current.line, current.column)

    def _advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def _expect(self, kind: TokenKind, message: str) -> Token:
        if self.current.kind is not kind:
            token = self.current
            raise ParseError(message, token.line, token.column)
        return self._advance()

    def _match(self, kind: TokenKind) -> Token | None:
        if self.current.kind is kind:
            return self._advance()
        return None

    def _parse_function(self) -> Function:
        keyword = self._expect(TokenKind.FUNC, "expected 'func' to start a function")
        name = self._expect(TokenKind.IDENT, "expected a function name after 'func'").value
        self._expect(TokenKind.LPAREN, "expected '(' after the function name")
        parameters = self._parse_parameters()
        self._expect(TokenKind.RPAREN, "expected ')' after the parameter list")
        self._expect(TokenKind.LBRACE, "expected '{' to start the function body")
        body = self._parse_block()
        return Function(name, parameters, body, self._location(keyword))

    def _parse_parameters(self) -> list[str]:
        parameters: list[str] = []
        if self.current.kind is TokenKind.RPAREN:
            return parameters
        while True:
            parameters.append(
                self._expect(TokenKind.IDENT, "expected a parameter name").value
            )
            if self._match(TokenKind.COMMA) is None:
                return parameters

    def _parse_block(self) -> list[Statement]:
        body: list[Statement] = []
        while self.current.kind is not TokenKind.RBRACE:
            if self.current.kind is TokenKind.EOF:
                token = self.current
                raise ParseError("unclosed block", token.line, token.column)
            body.append(self._parse_statement())
        self._advance()
        return body

    def _parse_statement(self) -> Statement:
        if self.current.kind in (TokenKind.LET, TokenKind.MUT):
            keyword = self._advance()
            is_mut = keyword.kind is TokenKind.MUT
            if is_mut is False and self.current.kind is TokenKind.MUT:
                token = self.current
                raise ParseError(
                    "mutable bindings are declared with 'mut name = value' "
                    "without 'let'",
                    token.line,
                    token.column,
                )
            name = self._expect(
                TokenKind.IDENT, "expected a variable name after the declaration"
            ).value
            self._expect(TokenKind.EQUAL, "expected '=' after the variable name")
            return LetStatement(
                self._location(keyword),
                name,
                self._parse_expression(),
                is_mut,
            )

        if (keyword := self._match(TokenKind.WHILE)) is not None:
            condition = self._parse_expression()
            self._expect(TokenKind.LBRACE, "expected '{' after the while condition")
            body = self._parse_block()
            return WhileStatement(self._location(keyword), condition, body)

        if (keyword := self._match(TokenKind.IF)) is not None:
            condition = self._parse_expression()
            self._expect(TokenKind.LBRACE, "expected '{' after the if condition")
            then_branch = self._parse_block()
            else_branch = None
            if self._match(TokenKind.ELSE) is not None:
                self._expect(TokenKind.LBRACE, "expected '{' after 'else'")
                else_branch = self._parse_block()
            return IfStatement(
                self._location(keyword), condition, then_branch, else_branch
            )

        if self.current.kind is TokenKind.IDENT:
            if (
                self.index + 1 < len(self.tokens)
                and self.tokens[self.index + 1].kind is TokenKind.EQUAL
            ):
                name_token = self._advance()
                self._expect(TokenKind.EQUAL, "expected '=' after the variable name")
                return AssignStatement(
                    self._location(name_token),
                    name_token.value,
                    self._parse_expression(),
                )

        expression = self._parse_expression()
        if isinstance(expression, IndexExpr) and self.current.kind is TokenKind.EQUAL:
            self._advance()
            return IndexAssignStatement(
                expression.location,
                expression.collection,
                expression.index,
                self._parse_expression(),
            )
        return ExpressionStatement(expression.location, expression)

    def _parse_expression(self) -> Expr:
        return self._parse_equality()

    def _parse_equality(self) -> Expr:
        expression = self._parse_relational()
        while self.current.kind is TokenKind.EQEQ:
            operator_token = self._advance()
            expression = BinaryExpr(
                self._location(operator_token),
                operator_token.value,
                expression,
                self._parse_relational(),
            )
        return expression

    def _parse_relational(self) -> Expr:
        expression = self._parse_additive()
        while self.current.kind in (TokenKind.LT, TokenKind.GT):
            operator_token = self._advance()
            expression = BinaryExpr(
                self._location(operator_token),
                operator_token.value,
                expression,
                self._parse_additive(),
            )
        return expression

    def _parse_additive(self) -> Expr:
        expression = self._parse_multiplicative()
        while self.current.kind in (TokenKind.PLUS, TokenKind.MINUS):
            operator_token = self._advance()
            expression = BinaryExpr(
                self._location(operator_token),
                operator_token.value,
                expression,
                self._parse_multiplicative(),
            )
        return expression

    def _parse_multiplicative(self) -> Expr:
        expression = self._parse_postfix()
        while self.current.kind in (TokenKind.STAR, TokenKind.SLASH):
            operator_token = self._advance()
            expression = BinaryExpr(
                self._location(operator_token),
                operator_token.value,
                expression,
                self._parse_postfix(),
            )
        return expression

    def _parse_postfix(self) -> Expr:
        expression = self._parse_primary()
        while True:
            if (token := self._match(TokenKind.LPAREN)) is not None:
                if not isinstance(expression, NameExpr):
                    raise ParseError(
                        "only function names can be called",
                        token.line,
                        token.column,
                    )
                expression = CallExpr(
                    self._location(token), expression.name, self._parse_arguments()
                )
            elif (token := self._match(TokenKind.LBRACKET)) is not None:
                index = self._parse_expression()
                self._expect(TokenKind.RBRACKET, "expected ']' after the index")
                expression = IndexExpr(self._location(token), expression, index)
            else:
                break
        return expression

    def _parse_primary(self) -> Expr:
        token = self.current
        if self._match(TokenKind.NUMBER) is not None:
            return NumberExpr(self._location(token), int(token.value))
        if self._match(TokenKind.STRING) is not None:
            return StringExpr(self._location(token), token.value)
        if self._match(TokenKind.IDENT) is not None:
            return NameExpr(self._location(token), token.value)
        if self._match(TokenKind.LBRACKET) is not None:
            elements = []
            if self.current.kind is not TokenKind.RBRACKET:
                while True:
                    elements.append(self._parse_expression())
                    if self._match(TokenKind.COMMA) is None:
                        break
            self._expect(TokenKind.RBRACKET, "expected ']' after the array elements")
            return ArrayExpr(self._location(token), elements)
        if self._match(TokenKind.LPAREN) is not None:
            expression = self._parse_expression()
            self._expect(TokenKind.RPAREN, "expected ')' after the expression")
            return expression
        raise ParseError(
            f"expected an expression, got {token.value!r}",
            token.line,
            token.column,
        )

    def _parse_arguments(self) -> list[Expr]:
        arguments: list[Expr] = []
        if self.current.kind is not TokenKind.RPAREN:
            while True:
                arguments.append(self._parse_expression())
                if self._match(TokenKind.COMMA) is None:
                    break
        self._expect(TokenKind.RPAREN, "expected ')' after the arguments")
        return arguments
