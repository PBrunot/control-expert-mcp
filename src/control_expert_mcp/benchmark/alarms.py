"""Restricted offline ST transition proof for the demo-derived alarm task.

Only Boolean assignments/IFs and comparisons of the converted INT temperature
with constants are supported. No PLC execution or ALRM_DIA emulation is claimed.
"""
from __future__ import annotations

import math
import re

FLAGS = {"temp_fault_1", "temp_fault_2"}
BOOLS = FLAGS | {"start_process"}
TOKEN = re.compile(r"\s+|[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|:=|<=|>=|<>|[();=<>+\-,]")

CANONICAL = """
(* Demo-derived training extension: hysteretic temperature alarms. *)
IF NOT Start_process THEN
    Temp_fault_1 := FALSE;
    Temp_fault_2 := FALSE;
ELSE
    IF Cmeasured_temp <= 200.0 THEN
        Temp_fault_1 := TRUE;
    ELSIF Cmeasured_temp >= 205.0 THEN
        Temp_fault_1 := FALSE;
    END_IF;
    IF Cmeasured_temp >= 400.0 THEN
        Temp_fault_2 := TRUE;
    ELSIF Cmeasured_temp <= 395.0 THEN
        Temp_fault_2 := FALSE;
    END_IF;
END_IF;
"""


def tokens(text: str) -> list[str]:
    """Tokenize without silently discarding unsupported operators or syntax."""
    text = re.sub(r"\(\*.*?\*\)|//[^\n]*", " ", text, flags=re.S)
    result, position = [], 0
    for match in TOKEN.finditer(text):
        if match.start() != position:
            raise ValueError("Unsupported ST token")
        position = match.end()
        if not match[0].isspace():
            result.append(match[0].lower())
    if position != len(text):
        raise ValueError("Unsupported ST suffix")
    return result


class Parser:
    """Small typed grammar, deliberately excluding arithmetic, calls and loops."""

    def __init__(self, values: list[str]):
        self.values, self.position, self.constants = values, 0, set()

    def peek(self):
        return self.values[self.position] if self.position < len(self.values) else ""

    def take(self, expected=None):
        value = self.peek()
        if not value or (expected is not None and value != expected):
            raise ValueError("Unsupported ST structure")
        self.position += 1
        return value

    def expression(self, precedence=0):
        operators = {"or": 1, "and": 2, "=": 3, "<>": 3,
                     "<": 3, ">": 3, "<=": 3, ">=": 3}
        value = self.take()
        if value == "not":
            node = ("not", self.expression(4))
        elif value == "(":
            node = self.expression()
            self.take(")")
        elif value in {"true", "false"}:
            node = ("bool", value == "true")
        elif value in BOOLS or value == "cmeasured_temp":
            node = ("input", value)
        else:
            sign = -1 if value == "-" else 1
            if value in {"-", "+"}:
                value = self.take()
            if not re.fullmatch(r"\d+(?:\.\d+)?", value):
                raise ValueError("Unsupported alarm expression")
            number = sign * float(value)
            if not math.isfinite(number) or abs(number) > 32768:
                raise ValueError("Alarm constant outside supported range")
            self.constants.add(number)
            node = ("number", number)
        while operators.get(self.peek(), -1) >= precedence:
            operator = self.take()
            node = (operator, node, self.expression(operators[operator] + 1))
        return node

    def block(self):
        statements = []
        while self.peek() and self.peek() not in {"else", "elsif", "end_if"}:
            if self.peek() == "if":
                self.take("if")
                branches = []
                while True:
                    condition = self.expression()
                    require_boolean(condition)
                    self.take("then")
                    branches.append((condition, self.block()))
                    if self.peek() != "elsif":
                        break
                    self.take("elsif")
                otherwise = []
                if self.peek() == "else":
                    self.take("else")
                    otherwise = self.block()
                self.take("end_if")
                self.take(";")
                statements.append(("if", branches, otherwise))
            else:
                target = self.take()
                if target not in FLAGS:
                    raise ValueError("Alarm extension may only assign the two fault flags")
                self.take(":=")
                expression = self.expression()
                require_boolean(expression)
                self.take(";")
                statements.append(("assign", target, expression))
        return statements


def expression_type(node) -> str:
    op = node[0]
    if op in {"bool", "number"}:
        return op
    if op == "input":
        return "number" if node[1] == "cmeasured_temp" else "bool"
    if op == "not":
        require_boolean(node[1])
    elif op in {"and", "or"}:
        require_boolean(node[1])
        require_boolean(node[2])
    elif expression_type(node[1]) != "number" or expression_type(node[2]) != "number":
        raise ValueError("Only numeric comparisons are supported")
    return "bool"


def require_boolean(node):
    if expression_type(node) != "bool":
        raise ValueError("Expected Boolean alarm expression")


def value(node, state):
    op = node[0]
    if op in {"bool", "number"}:
        return node[1]
    if op == "input":
        return state[node[1]]
    left = value(node[1], state)
    if op == "not":
        return not left
    right = value(node[2], state)
    return {"and": lambda: left and right, "or": lambda: left or right,
            "=": lambda: left == right, "<>": lambda: left != right,
            "<": lambda: left < right, ">": lambda: left > right,
            "<=": lambda: left <= right, ">=": lambda: left >= right}[op]()


def execute(statements, state):
    for statement in statements:
        if statement[0] == "assign":
            state[statement[1]] = value(statement[2], state)
        else:
            for condition, branch in statement[1]:
                if value(condition, state):
                    execute(branch, state)
                    break
            else:
                execute(statement[2], state)


def alarm_grade(baseline: str, actual: str) -> dict:
    """Prove every supported INT-input transition by constant partitions.

    With no arithmetic, each numeric comparison is constant between its literal
    boundaries. Checking boundary neighbors covers every INT input; enumerating
    both previous flags and enable states proves the one-scan transition table.
    """
    result = {"rubric": "feeder-alarms-1", "scope": "unverified",
              "static_behavior": "unverified", "runtime_behavior": "unverified",
              "method": "restricted ST interpreter + exhaustive INT comparison partitions; no PLC execution"}
    try:
        original, candidate = tokens(baseline), tokens(actual)
        if candidate[:len(original)] != original:
            return result
        parser = Parser(candidate[len(original):])
        statements = parser.block()
        if parser.position != len(parser.values) or not statements:
            return result
        result["scope"] = "pass"
        points = {-32768, 32767}
        for constant in parser.constants | {200, 205, 395, 400}:
            for point in (math.floor(constant), math.ceil(constant)):
                points.update(x for x in (point - 1, point, point + 1) if -32768 <= x <= 32767)
        checked = 0
        for measured in sorted(points):
            for enabled in (False, True):
                for low in (False, True):
                    for high in (False, True):
                        state = {"cmeasured_temp": float(measured), "start_process": enabled,
                                 "temp_fault_1": low, "temp_fault_2": high}
                        execute(statements, state)
                        expected_low = enabled and (measured <= 200 or (low and measured < 205))
                        expected_high = enabled and (measured >= 400 or (high and measured > 395))
                        checked += 1
                        if (state["temp_fault_1"], state["temp_fault_2"]) != (expected_low, expected_high):
                            result["counterexample"] = {"measured": measured, "enabled": enabled,
                                "prior_low": low, "prior_high": high,
                                "expected_low": expected_low, "expected_high": expected_high,
                                "actual_low": state["temp_fault_1"], "actual_high": state["temp_fault_2"]}
                            return result
        result.update(static_behavior="pass", partition_cases=checked, int_domain=[-32768, 32767])
    except (ValueError, RecursionError):
        pass  # Unsupported syntax stays unverified; never silently accept it.
    return result
