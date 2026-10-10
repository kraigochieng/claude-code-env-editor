"""The kind of secret variable an endpoint expects."""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

AuthKind: TypeAlias = Literal["api_key", "auth_token"]

VARIABLE_OF: Final[dict[AuthKind, str]] = {"api_key": "ANTHROPIC_API_KEY", "auth_token": "ANTHROPIC_AUTH_TOKEN"}
HEADER_OF: Final[dict[AuthKind, str]] = {"api_key": "x-api-key", "auth_token": "Authorization: Bearer"}
