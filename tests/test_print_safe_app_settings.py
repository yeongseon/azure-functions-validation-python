"""Tests for scripts/print_safe_app_settings.py (issue #544).

The E2E certification workflow's diagnostic step must never render a secret
value (storage connection strings, account keys, function keys, ...) to the
workflow log. These tests exercise the script with synthetic, clearly-dummy
app settings -- no real credentials, no Azure CLI call, no deployment.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pytest

from scripts.print_safe_app_settings import (
    SAFE_SETTING_NAMES,
    main,
    render_safe_app_settings,
)

_DUMMY_STORAGE_KEY = "dGhpcy1pcy1hLWR1bW15LWtleS1ub3QtcmVhbA=="
_DUMMY_SECRET = "synthetic-super-secret-value"


def _settings(**names_to_values: str) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in names_to_values.items()]


class TestRenderSafeAppSettings:
    def test_secret_bearing_values_are_never_rendered(self) -> None:
        settings = _settings(
            AzureWebJobsStorage=(
                f"DefaultEndpointsProtocol=https;AccountName=fake;"
                f"AccountKey={_DUMMY_STORAGE_KEY};EndpointSuffix=core.windows.net"
            ),
            MY_CUSTOM_SECRET=_DUMMY_SECRET,
        )

        output = render_safe_app_settings(settings)

        assert _DUMMY_STORAGE_KEY not in output
        assert _DUMMY_SECRET not in output
        assert "AzureWebJobsStorage = <hidden>" in output
        assert "MY_CUSTOM_SECRET = <hidden>" in output

    def test_allowlisted_safe_settings_are_rendered_with_their_value(self) -> None:
        settings = _settings(FUNCTIONS_EXTENSION_VERSION="~4", FUNCTIONS_WORKER_RUNTIME="python")

        output = render_safe_app_settings(settings)

        assert "FUNCTIONS_EXTENSION_VERSION = ~4" in output
        assert "FUNCTIONS_WORKER_RUNTIME = python" in output

    def test_unknown_new_setting_defaults_to_hidden(self) -> None:
        """Regression guard: a setting the allowlist has never seen before
        must be names-only, not rendered -- the allowlist is a safelist, not
        a blocklist of currently-known secret names.
        """
        settings = _settings(SOME_BRAND_NEW_SETTING_NO_ONE_CLASSIFIED_YET="could-be-anything")

        output = render_safe_app_settings(settings)

        assert "could-be-anything" not in output
        assert "SOME_BRAND_NEW_SETTING_NO_ONE_CLASSIFIED_YET = <hidden>" in output

    def test_setting_names_are_always_present(self) -> None:
        """Troubleshooting value: names (safe or not) must still be visible."""
        settings = _settings(AzureWebJobsStorage="irrelevant", FUNCTIONS_WORKER_RUNTIME="python")

        output = render_safe_app_settings(settings)

        assert "AzureWebJobsStorage" in output
        assert "FUNCTIONS_WORKER_RUNTIME" in output

    def test_empty_settings_list_renders_empty_output(self) -> None:
        assert render_safe_app_settings([]) == ""


class TestSafeSettingNamesAllowlist:
    def test_known_secret_bearing_names_are_not_on_the_allowlist(self) -> None:
        assert "AzureWebJobsStorage" not in SAFE_SETTING_NAMES
        assert "APPINSIGHTS_INSTRUMENTATIONKEY" not in SAFE_SETTING_NAMES
        assert "APPLICATIONINSIGHTS_CONNECTION_STRING" not in SAFE_SETTING_NAMES


class TestMainCli:
    def test_main_reads_stdin_and_prints_safe_output(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _settings(
            AzureWebJobsStorage=f"AccountKey={_DUMMY_STORAGE_KEY}",
            FUNCTIONS_WORKER_RUNTIME="python",
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(settings)))

        exit_code = main([])

        captured = capsys.readouterr()
        assert exit_code == 0
        assert _DUMMY_STORAGE_KEY not in captured.out
        assert "FUNCTIONS_WORKER_RUNTIME = python" in captured.out

    def test_main_reads_from_input_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps(_settings(MY_SECRET=_DUMMY_SECRET, FUNCTIONS_WORKER_RUNTIME="python"))
        )

        exit_code = main(["--input", str(settings_file)])

        captured = capsys.readouterr()
        assert exit_code == 0
        assert _DUMMY_SECRET not in captured.out
        assert "FUNCTIONS_WORKER_RUNTIME = python" in captured.out

    def test_main_rejects_non_list_json(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"not": "a list"}))

        exit_code = main(["--input", str(settings_file)])

        assert exit_code == 1
