"""A tiny, safe boolean/arithmetic expression language for scenario conditions.

Names are device references (X20, D112, T22), `<DEV>_value` word reads, or plant signals (P_kpa).
Only boolean operators, comparisons, + - * / and numeric/bool constants are allowed — no calls,
attributes, subscripts or strings — so scenario files cannot execute code.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from types import CodeType
from typing import Callable

_ALLOWED = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
            ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Name, ast.Load,
            ast.Constant, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div)


class ExprError(ValueError):
    """An expression outside the allowed grammar, or a name that cannot be resolved."""


@dataclass(frozen=True)
class Expr:
    text: str
    names: tuple[str, ...]
    code: CodeType = field(repr=False, compare=False)

    def __reduce__(self):  # code objects do not pickle; rebuild from the source text in worker processes
        return (compile_expr, (self.text,))


def compile_expr(text: str) -> Expr:
    try:
        tree = ast.parse(str(text), mode="eval")
    except SyntaxError as e:
        raise ExprError(f"{text!r}: {e.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ExprError(f"{text!r}: {type(node).__name__} is not allowed in scenario expressions")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (bool, int, float)):
            raise ExprError(f"{text!r}: only numeric and boolean constants are allowed")
    names = tuple(sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}))
    return Expr(str(text), names, compile(tree, "<scenario-expr>", "eval"))


def evaluate(expr: Expr, resolve: Callable[[str], object]):
    env = {name: resolve(name) for name in expr.names}
    return eval(expr.code, {"__builtins__": {}}, env)  # noqa: S307 — AST whitelisted above
