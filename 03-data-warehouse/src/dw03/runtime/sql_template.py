# src/dw03/runtime/sql_template.py
from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined


# Initialize Jinja2 environment with strict variable checking and whitespace control
_ENV = Environment(
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def render_sql_template(sql_text: str, variables: dict[str, Any]) -> str:
    """
    Renders SQL with full Jinja2 support (logic, loops, and variables).
    Uses StrictUndefined to raise an error immediately if a variable is missing.
    """
    template = _ENV.from_string(sql_text)
    return template.render(**variables)