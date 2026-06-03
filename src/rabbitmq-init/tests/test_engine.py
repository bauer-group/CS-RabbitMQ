"""Unit tests for the pure helpers in rmq.py (no broker required)."""

import os

import pytest

from rmq import binding_matches, enc, resolve_config_values, resolve_env_vars


# --- resolve_env_vars --------------------------------------------------------

def test_resolve_env_vars_substitutes(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cr3t")
    assert resolve_env_vars("${APP_PASSWORD}") == "s3cr3t"
    assert resolve_env_vars("pre-${APP_PASSWORD}-post") == "pre-s3cr3t-post"


def test_resolve_env_vars_missing_raises(monkeypatch):
    monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
    with pytest.raises(ValueError):
        resolve_env_vars("${DOES_NOT_EXIST}")


def test_resolve_env_vars_no_placeholder_is_passthrough():
    assert resolve_env_vars("plain-value") == "plain-value"


# --- resolve_config_values ---------------------------------------------------

def test_resolve_config_values_nested(monkeypatch):
    monkeypatch.setenv("APP_USER", "app")
    monkeypatch.setenv("APP_PASSWORD", "pw")
    cfg = {
        "users": [
            {"name": "${APP_USER}", "password": "${APP_PASSWORD}", "tags": ["management"]}
        ],
        "count": 3,
        "enabled": True,
    }
    out = resolve_config_values(cfg)
    assert out["users"][0]["name"] == "app"
    assert out["users"][0]["password"] == "pw"
    # Non-string types are passed through untouched.
    assert out["count"] == 3
    assert out["enabled"] is True
    assert out["users"][0]["tags"] == ["management"]


def test_resolve_config_values_skips_comment_keys():
    # '_'-prefixed keys are comments — never resolved, even with ${...} inside.
    cfg = {"_comment": "use ${VAR} placeholders", "name": "static"}
    out = resolve_config_values(cfg)
    assert out["_comment"] == "use ${VAR} placeholders"
    assert out["name"] == "static"


# --- binding_matches ---------------------------------------------------------

def test_binding_matches_routing_key_and_args():
    existing = {"routing_key": "notify.#", "arguments": {}}
    assert binding_matches(existing, "notify.#", {})
    assert not binding_matches(existing, "other.#", {})


def test_binding_matches_treats_empty_equivalently():
    # API may omit routing_key/arguments; missing == "" / {}.
    assert binding_matches({}, "", {})
    assert binding_matches({}, "", None)
    assert not binding_matches({}, "x", {})


def test_binding_matches_arguments_compared():
    existing = {"routing_key": "k", "arguments": {"x-match": "all"}}
    assert binding_matches(existing, "k", {"x-match": "all"})
    assert not binding_matches(existing, "k", {"x-match": "any"})


# --- enc ---------------------------------------------------------------------

def test_enc_encodes_default_vhost():
    assert enc("/") == "%2F"
    assert enc("applications") == "applications"
    assert enc("a/b") == "a%2Fb"
