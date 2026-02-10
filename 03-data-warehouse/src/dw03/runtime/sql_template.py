# src/dw03/runtime/sql_template.py
from __future__ import annotations

import re

_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render_sql_template(sql: str, variables: dict[str, str]) -> str:
    """
    Very small templating:
      SELECT * FROM `{{project_id}}.{{dataset}}.table`

    If a placeholder is missing -> raise (fail-fast).
    """

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"Missing SQL template variable: '{key}'")
        return str(variables[key])

    return _PATTERN.sub(repl, sql)
