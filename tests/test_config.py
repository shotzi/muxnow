"""Tests for configuration loading."""

import os
from muxnow.config import MuxnowConfig


def test_default_config():
    config = MuxnowConfig()
    assert config.model.base_url == "http://127.0.0.1:4000/v1"
    assert config.model.model == "deepseek-flash"
    assert config.model.api_key is None
    assert config.capture.fail_closed is True
    assert len(config.capture.redact_patterns) > 0
    assert len(config.guard.deny_patterns) > 0


def test_custom_toml_config_with_api_key(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[model]
base_url = "http://192.168.70.20:4000/v1"
model = "deepseek-flash"
api_key = "sk-test-token-12345"
timeout_s = 45.0
context_blocks = 8

[capture]
fail_closed = false

[audit]
path = "/tmp/muxnow_audit.jsonl"
""")

    loaded = MuxnowConfig.load(config_file)
    assert loaded.model.base_url == "http://192.168.70.20:4000/v1"
    assert loaded.model.model == "deepseek-flash"
    assert loaded.model.api_key == "sk-test-token-12345"
    assert loaded.model.timeout_s == 45.0
    assert loaded.model.context_blocks == 8
    assert loaded.capture.fail_closed is False
    assert loaded.audit.path == "/tmp/muxnow_audit.jsonl"


def test_api_key_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MUXNOW_API_KEY", "sk-env-token-xyz")
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[model]
model = "deepseek-flash"
""")
    loaded = MuxnowConfig.load(config_file)
    assert loaded.model.api_key == "sk-env-token-xyz"
