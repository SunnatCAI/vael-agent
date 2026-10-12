"""Regression tests for #106336: Desktop-saved registry-provider credentials.

The Desktop settings UI persists a registry provider's API key as a credential
pointer — ``model.key_env`` in config.yaml → the env var in ``$VAEL_HOME/.env``
(e.g. ``VAEL_CUSTOM_LMSTUDIO_API_KEY``) — while keeping ``model.provider`` on
the registry id. Before the fix, ``_resolve_api_key_provider_secret`` consulted
only ``PROVIDER_REGISTRY[...].api_key_env_vars``, silently ignored the UI-saved
key, and lmstudio fell through to its no-auth placeholder (``dummy-lm-api-key``),
producing an opaque 401 against auth-enabled LM Studio servers.
"""

from pathlib import Path

import pytest


@pytest.fixture
def vael_home(tmp_path, monkeypatch):
    home = tmp_path / ".vael"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("VAEL_HOME", str(home))
    monkeypatch.delenv("LM_API_KEY", raising=False)
    monkeypatch.delenv("VAEL_CUSTOM_LMSTUDIO_API_KEY", raising=False)
    return home


def _write(home: Path, config: str, env: str) -> None:
    (home / "config.yaml").write_text(config, encoding="utf-8")
    (home / ".env").write_text(env, encoding="utf-8")


def test_model_key_env_pointer_is_honored_for_registry_provider(vael_home):
    _write(
        vael_home,
        "model:\n  default: some-model\n  provider: lmstudio\n"
        "  base_url: http://127.0.0.1:1234/v1\n"
        "  key_env: VAEL_CUSTOM_LMSTUDIO_API_KEY\n",
        "VAEL_CUSTOM_LMSTUDIO_API_KEY=sk-lm-desktop-saved\n",
    )
    from vael_cli.auth import resolve_api_key_provider_credentials

    creds = resolve_api_key_provider_credentials("lmstudio")
    assert creds["api_key"] == "sk-lm-desktop-saved"
    assert creds["source"] == "VAEL_CUSTOM_LMSTUDIO_API_KEY"


def test_model_key_env_does_not_leak_across_providers(vael_home):
    # model targets a DIFFERENT provider: its key_env must not be consulted for
    # lmstudio, which falls back to its documented no-auth placeholder.
    _write(
        vael_home,
        "model:\n  default: gpt-x\n  provider: openai\n"
        "  key_env: VAEL_CUSTOM_LMSTUDIO_API_KEY\n",
        "VAEL_CUSTOM_LMSTUDIO_API_KEY=sk-lm-should-not-leak\n",
    )
    from vael_cli.auth import LMSTUDIO_NOAUTH_PLACEHOLDER, resolve_api_key_provider_credentials

    creds = resolve_api_key_provider_credentials("lmstudio")
    assert creds["api_key"] == LMSTUDIO_NOAUTH_PLACEHOLDER
