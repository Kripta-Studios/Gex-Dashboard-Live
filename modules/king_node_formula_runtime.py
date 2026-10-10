"""Read-only evaluation of the pinned workbook expressions, never saved results.

The parser accepts only Excel literals, cell references, operators and an explicit
function vocabulary. There is no Python eval, file access, macro or external link.
Excel scalar/array semantics come from the pinned formulas library. IF/IFERROR are
lazy so unused branches do not create false circular dependencies.
"""

from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache

import numpy as np
import schedula as sh
from formulas.functions import get_functions
from formulas.functions.operators import OPERATORS
from formulas.tokens.operand import Error, XlError

FUNCTIONS = frozenset(
    [
        "IF",
        "AND",
        "INDEX",
        "N",
        "OR",
        "IFERROR",
        "ISNUMBER",
        "MATCH",
        "ABS",
        "NOT",
        "COUNTIF",
        "MAX",
        "SEARCH",
        "CHAR",
        "TEXT",
        "MIN",
        "SUMPRODUCT",
        "UPPER",
        "SUBSTITUTE",
        "ROUND",
        "REPT",
        "SIGN",
        "LEFT",
        "MID",
        "COUNT",
        "FIND",
        "MEDIAN",
        "TRIM",
        "MROUND",
        "FALSE",
        "LARGE",
        "VALUE",
        "LEN",
        "TRUE",
        "LOOKUP",
        "SUM",
        "ROW",
        "CHOOSE",
        "SUMIF",
        "COUNTIFS",
        "ROWS",
        "SUMIFS",
        "PROPER",
        "PERCENTILE",
        "VLOOKUP",
        "SMALL",
        "COUNTA",
        "CEILING",
        "FLOOR",
    ]
)
TOKEN = re.compile(
    r"""\s*("(?:[^"]|"")*"|(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z_0-9 .]*)!\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?|\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?|\d+(?:\.\d*)?(?:[Ee][+-]?\d+)?|\.\d+|[A-Za-z_][A-Za-z_0-9.]*|<>|<=|>=|[+*/^&=<>%(),{};:\-])"""
)
REF = re.compile(r"(?:(.+)!)?(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?$")
PRECEDENCE = {
    "=": 1,
    "<>": 1,
    "<": 1,
    ">": 1,
    "<=": 1,
    ">=": 1,
    "&": 2,
    "+": 3,
    "-": 3,
    "*": 4,
    "/": 4,
    "^": 5,
}


def col_number(label):
    n = 0
    for c in label:
        n = n * 26 + ord(c) - 64
    return n


def col_label(n):
    text = ""
    while n:
        n, rem = divmod(n - 1, 26)
        text = chr(65 + rem) + text
    return text


def coordinates(ref):
    col, row = re.fullmatch(r"([A-Z]+)(\d+)", ref.replace("$", "")).groups()
    return col_number(col), int(row)


def scalar(value):
    if isinstance(value, np.ndarray) and value.size == 1:
        return value.item()
    if isinstance(value, np.generic):
        return value.item()
    return value


def is_error(value):
    return isinstance(scalar(value), XlError)


@lru_cache(maxsize=8192)
def parse(formula):
    source = formula.lstrip("=")
    tokens, pos = [], 0
    while pos < len(source):
        match = TOKEN.match(source, pos)
        if not match:
            if not source[pos:].strip():
                break
            raise ValueError(f"Unsupported formula token: {source[pos : pos + 60]!r}")
        tokens.append(match[1])
        pos = match.end()
    i = 0

    def expression(minimum=0):
        nonlocal i
        token = tokens[i]
        i += 1
        if token in ("+", "-"):
            node = ("op", "U" + token, (expression(6),))
        elif token == "(":
            node = expression()
            if tokens[i] != ")":
                raise ValueError("Unclosed formula group")
            i += 1
        elif token.startswith('"'):
            node = ("literal", token[1:-1].replace('""', '"'))
        elif REF.fullmatch(token):
            if i < len(tokens) and tokens[i] == ":":
                next_ref = tokens[i + 1]
                left = REF.fullmatch(token)
                right = REF.fullmatch(next_ref)
                if not right or left[1] != right[1]:
                    raise ValueError("Cross-sheet range is unsupported")
                token += ":" + right[2]
                i += 2
            node = ("ref", token)
        elif re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", token):
            node = ("literal", float(token))
        elif token.upper() in ("TRUE", "FALSE") and (
            i == len(tokens) or tokens[i] != "("
        ):
            node = ("literal", token.upper() == "TRUE")
        elif i < len(tokens) and tokens[i] == "(":
            name = token.upper()
            if name not in FUNCTIONS:
                raise ValueError(f"Unsupported Excel function: {name}")
            i += 1
            args = []
            while tokens[i] != ")":
                args.append(("literal", None) if tokens[i] == "," else expression())
                if tokens[i] != ",":
                    break
                i += 1
                if tokens[i] == ")":
                    args.append(("literal", None))
            if tokens[i] != ")":
                raise ValueError("Unclosed function arguments")
            i += 1
            node = ("call", name, tuple(args))
        elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.]*", token):
            node = ("literal", Error.errors["#NAME?"])
        else:
            raise ValueError(f"Unsupported formula expression: {token}")
        while i < len(tokens):
            op = tokens[i]
            if op == "%":
                i += 1
                node = ("op", "%", (node,))
                continue
            precedence = PRECEDENCE.get(op, -1)
            if precedence < minimum:
                break
            i += 1
            node = ("op", op, (node, expression(precedence + 1)))
        return node

    result = expression()
    if i != len(tokens):
        raise ValueError(f"Unparsed formula suffix: {tokens[i:]}")
    return result


class Workbook:
    """One calculation pass with explicit input cells and memoized dependencies."""

    def __init__(self, cells, inputs=None):
        self.cells = cells
        self.inputs = dict(inputs or {})
        self.cache = {}
        self.active = set()
        self.stack = []
        self.consumers = defaultdict(set)
        self.errors = {}

    def set(self, sheet, cell, value):
        key = (sheet, cell)
        if key in self.inputs and self.inputs[key] == value:
            return
        self.inputs[key] = value
        pending, seen = [key], set()
        while pending:
            changed = pending.pop()
            if changed in seen:
                continue
            seen.add(changed)
            self.cache.pop(changed, None)
            self.errors.pop("!".join(changed), None)
            pending.extend(self.consumers.get(changed, ()))

    def get(self, sheet, cell):
        key = (sheet, cell.replace("$", ""))
        if self.stack:
            self.consumers[key].add(self.stack[-1])
        if key in self.inputs:
            return self.inputs[key] if self.inputs[key] is not None else sh.EMPTY
        if key in self.cache:
            return self.cache[key]
        if key in self.active:
            raise ValueError(f"Circular workbook dependency: {sheet}!{cell}")
        record = self.cells.get(sheet, {}).get(key[1])
        if record is None:
            return sh.EMPTY
        # Export records contain either a formula OR a constant, never a cached result.
        if "formula" not in record:
            return record.get("value") if record.get("value") is not None else sh.EMPTY
        self.active.add(key)
        self.stack.append(key)
        try:
            result = scalar(self.evaluate(parse(record["formula"]), sheet, cell))
            self.cache[key] = result
            if is_error(result):
                self.errors[f"{sheet}!{cell}"] = str(result)
            return result
        finally:
            self.active.remove(key)
            self.stack.pop()

    def reference(self, text, sheet):
        ref_sheet, start, end = REF.fullmatch(text).groups()
        if ref_sheet:
            sheet = ref_sheet.strip("'").replace("''", "'")
        if end is None:
            return self.get(sheet, start)
        c1, r1 = coordinates(start)
        c2, r2 = coordinates(end)
        if (c2 - c1 + 1) * (r2 - r1 + 1) > 10000:
            raise ValueError("Workbook range exceeds calculation limit")
        return np.array(
            [
                [self.get(sheet, f"{col_label(c)}{r}") for c in range(c1, c2 + 1)]
                for r in range(r1, r2 + 1)
            ],
            dtype=object,
        )

    def evaluate(self, node, sheet, cell):
        kind, name, *rest = node
        if kind == "literal":
            return name
        if kind == "ref":
            return self.reference(name, sheet)
        args = rest[0]
        if kind == "op":
            return OPERATORS[name](*(self.evaluate(x, sheet, cell) for x in args))
        if name == "IF":
            condition = scalar(self.evaluate(args[0], sheet, cell))
            if is_error(condition):
                return condition
            if not isinstance(condition, np.ndarray):
                branch = 1 if condition else 2
                return (
                    self.evaluate(args[branch], sheet, cell)
                    if len(args) > branch
                    else False
                )
        if name == "IFERROR":
            value = self.evaluate(args[0], sheet, cell)
            if not isinstance(value, np.ndarray) or value.size == 1:
                return self.evaluate(args[1], sheet, cell) if is_error(value) else value
        if name == "ROW":
            if not args:
                return coordinates(cell)[1]
            if args[0][0] != "ref":
                raise ValueError("ROW requires a cell reference")
            _, start, end = REF.fullmatch(args[0][1]).groups()
            return np.arange(
                coordinates(start)[1], coordinates(end or start)[1] + 1, dtype=object
            ).reshape(-1, 1)
        function = get_functions()[name]
        extra = []
        if isinstance(function, dict):
            extra = list(function.get("extra_inputs", {}).values())
            function = function["function"]
        return function(*extra, *(self.evaluate(x, sheet, cell) for x in args))
