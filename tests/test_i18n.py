"""Tests for i18n and language switching."""

from muxnow.config import MuxnowConfig
from muxnow.i18n import t
from muxnow.llm import build_system_prompt


def test_i18n_translations():
    # English default
    assert t("suggestion", "en") == "Suggestion"
    assert t("why", "en") == "Why"
    assert t("security", "en") == "Security"
    assert "English" in t("llm_instruction", "en")

    # German
    assert t("suggestion", "de") == "Vorschlag"
    assert t("why", "de") == "Warum"
    assert t("security", "de") == "Sicherheit"
    assert "Deutsch" in t("llm_instruction", "de")


def test_config_language_default():
    cfg = MuxnowConfig()
    assert cfg.language == "en"


def test_config_language_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
language = "de"
[model]
model = "deepseek-flash"
""")
    cfg = MuxnowConfig.load(config_file)
    assert cfg.language == "de"


def test_system_prompt_language():
    en_prompt = build_system_prompt("en")
    assert "English" in en_prompt

    de_prompt = build_system_prompt("de")
    assert "Deutsch" in de_prompt
