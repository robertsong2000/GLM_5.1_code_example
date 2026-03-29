"""
Expression Evaluator — 表达式解析与求值器

使用递归下降解析器（Recursive Descent Parser）实现，
支持完整的算术表达式求值，包含变量和函数调用。

支持的特性：
  • 四则运算 + 取模 + 幂运算:  +  -  *  /  %  **
  • 括号分组:  (1 + 2) * 3
  • 一元运算符:  -x, +x
  • 变量赋值与引用:  x = 10; x + 5
  • 内置函数:  sin, cos, sqrt, abs, log, max, min
  • 常量:  PI, E

语法（EBNF）:
  program    → statement ( ';' statement )*
  statement  → assignment | expr
  assignment → IDENT '=' expr
  expr       → term ( ('+' | '-') term )*
  term       → power ( ('*' | '/' | '%') power )*
  power      → unary ( '**' power )?
  unary      → ('-' | '+') unary | call
  call       → IDENT '(' args ')' | primary
  primary    → NUMBER | IDENT | '(' expr ')'
"""

from __future__ import annotations
import math
from enum import Enum, auto
from typing import Any


# ── Token ─────────────────────────────────────────────────

class TokenType(Enum):
    NUMBER    = auto()
    IDENT     = auto()
    PLUS      = auto()   # +
    MINUS     = auto()   # -
    STAR      = auto()   # *
    SLASH     = auto()   # /
    PERCENT   = auto()   # %
    POWER     = auto()   # **
    LPAREN    = auto()   # (
    RPAREN    = auto()   # )
    ASSIGN    = auto()   # =
    SEMI      = auto()   # ;
    COMMA     = auto()   # ,
    EOF       = auto()


class Token:
    __slots__ = ("type", "value", "pos")

    def __init__(self, type: TokenType, value: Any, pos: int):
        self.type = type
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r})"


# ── Lexer ─────────────────────────────────────────────────

class Lexer:
    """词法分析器：将源字符串拆分为 Token 流。"""

    def __init__(self, text: str):
        self._text = text
        self._pos = 0

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self._pos < len(self._text):
            ch = self._text[self._pos]

            if ch.isspace():
                self._pos += 1
                continue

            if ch.isdigit() or (ch == '.' and self._pos + 1 < len(self._text) and self._text[self._pos + 1].isdigit()):
                tokens.append(self._read_number())
                continue

            if ch.isalpha() or ch == '_':
                tokens.append(self._read_ident())
                continue

            token_map = {
                '+': TokenType.PLUS, '-': TokenType.MINUS,
                '*': TokenType.STAR, '/': TokenType.SLASH,
                '%': TokenType.PERCENT, '(': TokenType.LPAREN,
                ')': TokenType.RPAREN, '=': TokenType.ASSIGN,
                ';': TokenType.SEMI, ',': TokenType.COMMA,
            }

            # 处理 ** 幂运算符
            if ch == '*' and self._pos + 1 < len(self._text) and self._text[self._pos + 1] == '*':
                tokens.append(Token(TokenType.POWER, '**', self._pos))
                self._pos += 2
                continue

            if ch in token_map:
                tokens.append(Token(token_map[ch], ch, self._pos))
                self._pos += 1
                continue

            raise SyntaxError(f"意外的字符 '{ch}' 在位置 {self._pos}")

        tokens.append(Token(TokenType.EOF, None, self._pos))
        return tokens

    def _read_number(self) -> Token:
        start = self._pos
        has_dot = False
        while self._pos < len(self._text):
            ch = self._text[self._pos]
            if ch == '.' and not has_dot:
                has_dot = True
            elif ch.isdigit():
                pass
            else:
                break
            self._pos += 1
        return Token(TokenType.NUMBER, float(self._text[start:self._pos]), start)

    def _read_ident(self) -> Token:
        start = self._pos
        while self._pos < len(self._text) and (self._text[self._pos].isalnum() or self._text[self._pos] == '_'):
            self._pos += 1
        return Token(TokenType.IDENT, self._text[start:self._pos], start)


# ── AST Nodes ─────────────────────────────────────────────

class NumberNode:
    def __init__(self, value: float):
        self.value = value
    def __repr__(self):
        return f"{self.value}"

class VariableNode:
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return self.name

class BinaryOpNode:
    def __init__(self, op: str, left, right):
        self.op = op
        self.left = left
        self.right = right
    def __repr__(self):
        return f"({self.left} {self.op} {self.right})"

class UnaryOpNode:
    def __init__(self, op: str, operand):
        self.op = op
        self.operand = operand
    def __repr__(self):
        return f"({self.op}{self.operand})"

class CallNode:
    def __init__(self, name: str, args: list):
        self.name = name
        self.args = args
    def __repr__(self):
        return f"{self.name}({', '.join(str(a) for a in self.args)})"

class AssignNode:
    def __init__(self, name: str, expr):
        self.name = name
        self.expr = expr
    def __repr__(self):
        return f"{self.name} = {self.expr}"


# ── Parser ────────────────────────────────────────────────

class Parser:
    """递归下降解析器：将 Token 流解析为 AST。"""

    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> list:
        """解析整个程序，返回语句列表。"""
        statements: list = []
        while not self._at_end():
            statements.append(self._statement())
            if self._match(TokenType.SEMI):
                pass
        return statements

    def _statement(self):
        # 赋值: IDENT '=' expr
        if self._current().type == TokenType.IDENT and self._peek().type == TokenType.ASSIGN:
            name = self._current().value
            self._advance()  # skip ident
            self._advance()  # skip '='
            expr = self._expr()
            return AssignNode(name, expr)
        return self._expr()

    def _expr(self):
        """expr → term ( ('+' | '-') term )*"""
        left = self._term()
        while self._current().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._advance().value
            right = self._term()
            left = BinaryOpNode(op, left, right)
        return left

    def _term(self):
        """term → power ( ('*' | '/' | '%') power )*"""
        left = self._power()
        while self._current().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._advance().value
            right = self._power()
            left = BinaryOpNode(op, left, right)
        return left

    def _power(self):
        """power → unary ( '**' power )?  （右结合）"""
        base = self._unary()
        if self._current().type == TokenType.POWER:
            self._advance()
            exp = self._power()  # 右结合递归
            return BinaryOpNode('**', base, exp)
        return base

    def _unary(self):
        """unary → ('-' | '+') unary | call"""
        if self._current().type in (TokenType.MINUS, TokenType.PLUS):
            op = self._advance().value
            operand = self._unary()
            return UnaryOpNode(op, operand)
        return self._call()

    def _call(self):
        """call → IDENT '(' args ')' | primary"""
        if self._current().type == TokenType.IDENT and self._peek().type == TokenType.LPAREN:
            name = self._advance().value
            self._advance()  # skip '('
            args: list = []
            if self._current().type != TokenType.RPAREN:
                args.append(self._expr())
                while self._current().type == TokenType.COMMA:
                    self._advance()
                    args.append(self._expr())
            self._expect(TokenType.RPAREN)
            return CallNode(name, args)
        return self._primary()

    def _primary(self):
        """primary → NUMBER | IDENT | '(' expr ')'"""
        tok = self._current()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberNode(tok.value)
        if tok.type == TokenType.IDENT:
            self._advance()
            return VariableNode(tok.value)
        if tok.type == TokenType.LPAREN:
            self._advance()
            node = self._expr()
            self._expect(TokenType.RPAREN)
            return node
        raise SyntaxError(f"意外的标记 {tok} 在位置 {tok.pos}")

    # ── 辅助方法 ───────────────────────────────────

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self) -> Token:
        return self._tokens[min(self._pos + 1, len(self._tokens) - 1)]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if not self._at_end():
            self._pos += 1
        return tok

    def _at_end(self) -> bool:
        return self._current().type == TokenType.EOF

    def _match(self, type: TokenType) -> bool:
        if self._current().type == type:
            self._advance()
            return True
        return False

    def _expect(self, type: TokenType):
        if not self._match(type):
            raise SyntaxError(f"期望 {type.name}，得到 {self._current()}")


# ── Evaluator ─────────────────────────────────────────────

class Evaluator:
    """AST 求值器：遍历 AST 计算结果。"""

    BUILTINS: dict[str, Any] = {
        'PI': math.pi, 'E': math.e,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'sqrt': math.sqrt, 'abs': abs,
        'log': math.log, 'log2': math.log2, 'log10': math.log10,
        'ceil': math.ceil, 'floor': math.floor,
        'max': max, 'min': min,
        'round': round,
    }

    def __init__(self):
        self._vars: dict[str, float] = {}

    def eval_program(self, statements: list) -> list[float]:
        results: list[float] = []
        for stmt in statements:
            results.append(self._eval(stmt))
        return results

    def _eval(self, node) -> float:
        if isinstance(node, NumberNode):
            return node.value

        if isinstance(node, VariableNode):
            if node.name in self._vars:
                return self._vars[node.name]
            if node.name in self.BUILTINS:
                return self.BUILTINS[node.name]
            raise NameError(f"未定义的变量 '{node.name}'")

        if isinstance(node, AssignNode):
            val = self._eval(node.expr)
            self._vars[node.name] = val
            return val

        if isinstance(node, UnaryOpNode):
            val = self._eval(node.operand)
            return -val if node.op == '-' else val

        if isinstance(node, BinaryOpNode):
            left = self._eval(node.left)
            right = self._eval(node.right)
            ops = {
                '+': lambda a, b: a + b,
                '-': lambda a, b: a - b,
                '*': lambda a, b: a * b,
                '/': lambda a, b: a / b,
                '%': lambda a, b: a % b,
                '**': lambda a, b: a ** b,
            }
            return ops[node.op](left, right)

        if isinstance(node, CallNode):
            fn = self.BUILTINS.get(node.name)
            if fn is None:
                raise NameError(f"未定义的函数 '{node.name}'")
            args = [self._eval(a) for a in node.args]
            return fn(*args)

        raise RuntimeError(f"未知的 AST 节点: {type(node)}")


# ── 公开接口 ──────────────────────────────────────────────

def evaluate(source: str) -> list[float]:
    """
    求值一行或多行表达式（分号分隔）。

    >>> evaluate("1 + 2 * 3")
    [7.0]
    >>> evaluate("x = 10; y = 20; x + y")
    [10.0, 20.0, 30.0]
    >>> evaluate("sqrt(144) + 2 ** 3")
    [20.0]
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    return Evaluator().eval_program(ast)


# ── 演示 ──────────────────────────────────────────────────

def demo():
    print("=" * 60)
    print("  表达式解析求值器 演示")
    print("=" * 60)

    tests = [
        ("基本运算",   "1 + 2 * 3"),
        ("括号",       "(1 + 2) * 3"),
        ("幂运算",     "2 ** 10"),
        ("取模",       "17 % 5"),
        ("一元负号",   "-3 + 5"),
        ("右结合幂",   "2 ** 3 ** 2"),       # 2^(3^2) = 512
        ("变量赋值",   "x = 10; y = 20; x * y + 1"),
        ("内置函数",   "sqrt(144) + abs(-5)"),
        ("三角函数",   "sin(PI / 2) + cos(0)"),
        ("嵌套调用",   "max(sqrt(16), min(10, 20))"),
        ("复杂表达式", "(3 + 4) * (5 - 2) / 2 ** 2"),
    ]

    evaluator = Evaluator()

    for title, expr in tests:
        tokens = Lexer(expr).tokenize()
        ast = Parser(tokens).parse()
        results = evaluator.eval_program(ast)
        values_str = ", ".join(f"{r:g}" for r in results)
        print(f"\n  [{title}]")
        print(f"    输入:  {expr}")
        print(f"    AST:   {ast}")
        print(f"    结果:  {values_str}")

    # 交互式模式提示
    print("\n" + "=" * 60)
    print("  可使用 evaluate() 函数直接求值:")
    print("    evaluate('1 + 2 * 3')       → [7.0]")
    print("    evaluate('x=10; x**2+1')    → [10.0, 101.0]")
    print("    evaluate('sin(PI/6)')       → [0.5]")
    print("=" * 60)


if __name__ == "__main__":
    demo()
