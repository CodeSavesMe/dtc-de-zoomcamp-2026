# docker_ingestion_pipeline/utils/identifiers.py
from __future__ import annotations

import re

# PostgreSQL identifier rules (simplified):
# - must start with letter or underscore
# - followed by letters, digits, underscores
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_ident(name: str) -> str:
    """
    Normalize a raw identifier into a SQL-friendly form.

    This is useful when input comes from filenames or external schemas that may contain:
    - dashes, spaces, dots, etc.

    Example:
      "VendorID"      -> "vendorid"
      "pickup-date"   -> "pickup_date"
      "Rate Code"     -> "rate_code"
    """
    s = str(name).strip()

    # Replace common separators with underscore
    s = re.sub(r"[\s\-\.\:/]+", "_", s)

    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s)

    # Strip leading/trailing underscores
    s = s.strip("_")

    # Prefer lower-case for predictable SQL behavior
    s = s.lower()

    # Ensure non-empty
    if not s:
        raise ValueError(f"Identifier normalization produced empty string from: {name!r}")

    return s


def sanitize_ident(name: str) -> str:
    """
    Strictly validate identifier. Fail fast if unsafe.

    Use this for:
    - table names
    - schema names
    - column names that will be injected into SQL (even when quoted)
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def safe_ident(name: str) -> str:
    """
    Convenience helper: normalize then sanitize.

    Use this when identifiers originate from external sources.
    """
    return sanitize_ident(normalize_ident(name))


def qident(name: str) -> str:
    """
    Quote a validated identifier for SQL.

    Always call sanitize_ident() to prevent injection via identifier context.
    """
    return f'"{sanitize_ident(name)}"'
