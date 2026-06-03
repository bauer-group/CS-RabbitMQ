"""
Shared helpers for the RabbitMQ init container.

Contains:
  - Environment-variable resolution for ${VAR} placeholders in JSON config
  - A thin RabbitMQ Management HTTP API client (idempotent PUT helpers)
  - The binding-idempotency matcher used by the bindings task

Kept import-light (only `requests`) so the pure helpers can be unit-tested
without any running broker.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote

import requests

# Default vhost "/" must be percent-encoded to "%2F" in Management API paths.
DEFAULT_TIMEOUT = 10


# --- Environment variable resolution -----------------------------------------

_ENV_RE = re.compile(r"\$\{([^}]+)}")


def resolve_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} patterns with environment variable values.

    Raises ValueError if a referenced variable is not set, so misconfiguration
    fails loudly at startup rather than silently provisioning blank secrets.
    """
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"Environment variable '{var_name}' is not set")
        return env_value

    return _ENV_RE.sub(replacer, value)


def resolve_config_values(obj):
    """Recursively resolve environment variables in config values.

    Keys starting with '_' are treated as comments/metadata and passed through
    untouched (their values may legitimately contain literal ${...} examples).
    """
    if isinstance(obj, str):
        return resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {
            k: (v if k.startswith("_") else resolve_config_values(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [resolve_config_values(item) for item in obj]
    return obj


# --- Binding idempotency ------------------------------------------------------

def binding_matches(existing: dict, routing_key: str, arguments: dict | None) -> bool:
    """True if an existing binding equals the desired routing_key + arguments."""
    return (
        existing.get("routing_key", "") == (routing_key or "")
        and (existing.get("arguments") or {}) == (arguments or {})
    )


# --- URL encoding -------------------------------------------------------------

def enc(segment) -> str:
    """Percent-encode a single Management API path segment (vhost, name, ...)."""
    return quote(str(segment), safe="")


# --- Management HTTP API client ----------------------------------------------

def error_text(resp: requests.Response) -> str:
    """Extract a human-readable reason from a Management API error response."""
    try:
        data = resp.json()
        if isinstance(data, dict):
            reason = data.get("reason") or data.get("error")
            if reason:
                return str(reason)
    except ValueError:
        pass
    return (resp.text or f"HTTP {resp.status_code}").strip()


class RabbitMQClient:
    """Minimal RabbitMQ Management HTTP API client."""

    def __init__(self, base_url: str, user: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # -- low level --
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        return self.session.request(method, f"{self.base_url}{path}", **kwargs)

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def put(self, path: str, body: dict, **kwargs) -> requests.Response:
        return self.request("PUT", path, json=body, **kwargs)

    def post(self, path: str, body: dict, **kwargs) -> requests.Response:
        return self.request("POST", path, json=body, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    # -- helpers --
    def exists(self, path: str) -> bool:
        """True if a GET on the resource path returns 200."""
        return self.get(path).status_code == 200

    def put_resource(self, path: str, body: dict) -> tuple[str, requests.Response]:
        """GET-then-PUT a resource. Returns (state, response) where state is
        'created' | 'updated' | 'error'. PUT is idempotent regardless."""
        existed = self.exists(path)
        resp = self.put(path, body)
        if resp.status_code in (200, 201, 204):
            return ("updated" if existed else "created", resp)
        return ("error", resp)
