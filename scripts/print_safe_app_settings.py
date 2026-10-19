"""Print Azure Function App settings without leaking secret-bearing values.

The E2E certification workflow's diagnostic step needs to confirm which
application settings are present without ever rendering a secret value
(storage connection strings, account keys, function keys, and anything else
not explicitly known to be safe) to the workflow log (#544).

Reads a JSON array of app settings -- the exact shape produced by
``az functionapp config appsettings list -o json`` -- from stdin or a file,
and prints each setting's name on its own line; a value is ALSO printed only
when the setting's name is on an explicit, maintained allowlist of known-safe
runtime/version configuration. Any setting not on that allowlist -- including
a brand-new one this list has never seen -- is names-only. This is
deliberately a safelist, not a blocklist of currently-known secret names: a
newly introduced secret-bearing setting is hidden by default rather than
leaking until someone remembers to blocklist it.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import sys
from typing import Any

#: Setting names known to be non-secret runtime/version configuration, safe
#: to print verbatim for troubleshooting. Anything NOT in this set is
#: printed as name-only, regardless of whether it is currently a known
#: secret (#544) -- the allowlist, not a blocklist, is the safety boundary.
SAFE_SETTING_NAMES: frozenset[str] = frozenset(
    {
        "FUNCTIONS_EXTENSION_VERSION",
        "FUNCTIONS_WORKER_RUNTIME",
        "FUNCTIONS_WORKER_RUNTIME_VERSION",
        "WEBSITE_NODE_DEFAULT_VERSION",
        "SCM_DO_BUILD_DURING_DEPLOYMENT",
        "ENABLE_ORYX_BUILD",
        "AzureWebJobsFeatureFlags",
        "PYTHON_ISOLATE_WORKER_DEPENDENCIES",
    }
)

#: Known-safe sentinel values for ``WEBSITE_RUN_FROM_PACKAGE`` -- "run from
#: the zip deployed alongside the app". Any other value (notably a package
#: blob URL, which can carry a SAS token) is a secret shape and must render
#: as hidden (#564): this setting is not unconditionally safe like the
#: names in ``SAFE_SETTING_NAMES`` above, so it is intentionally excluded
#: from that set and checked separately.
_WEBSITE_RUN_FROM_PACKAGE_SAFE_VALUES: frozenset[str] = frozenset({"0", "1"})

_HIDDEN_PLACEHOLDER = "<hidden>"


def render_safe_app_settings(settings: list[dict[str, Any]]) -> str:
    """Return one ``name = value``/``name = <hidden>`` line per setting.

    Pure formatting function with no I/O, so it is directly unit-testable
    with synthetic data -- no ``az`` CLI call or Azure deployment required.
    """
    lines: list[str] = []
    for setting in settings:
        name = str(setting.get("name", "<unnamed>"))
        value = str(setting.get("value", ""))
        if name == "WEBSITE_RUN_FROM_PACKAGE":
            is_safe = value in _WEBSITE_RUN_FROM_PACKAGE_SAFE_VALUES
        else:
            is_safe = name in SAFE_SETTING_NAMES
        lines.append(f"{name} = {value}" if is_safe else f"{name} = {_HIDDEN_PLACEHOLDER}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Print app settings from stdin (or ``--input FILE``), names-only
    except for the explicit safe allowlist."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=argparse.FileType("r"),
        default=None,
        help=(
            "JSON file of app settings, shaped like "
            "`az functionapp config appsettings list -o json`; "
            "reads stdin when omitted"
        ),
    )
    arguments = parser.parse_args(argv)
    source = arguments.input if arguments.input is not None else sys.stdin
    try:
        settings = json.load(source)
    finally:
        if arguments.input is not None:
            arguments.input.close()

    if not isinstance(settings, list):
        print("expected a JSON array of app settings", file=sys.stderr)
        return 1

    print(render_safe_app_settings(settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
