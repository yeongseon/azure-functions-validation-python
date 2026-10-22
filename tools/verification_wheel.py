"""Install the built wheel and check schema/import identity outside the checkout."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile

from scripts.check_wheel_schemas import verify_wheel
from tools.verification_evidence import redact
from tools.verification_process import run


def main() -> int:
    directory = Path("test-results/wheel-smoke/logs")
    with tempfile.TemporaryDirectory(prefix="validation-wheel-") as temporary:
        root = Path(temporary)
        code = run(
            [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(root / "dist")],
            directory / "build.log",
        )
        if code:
            return code
        wheels = list((root / "dist").glob("*.whl"))
        if len(wheels) != 1:
            print("Expected exactly one freshly built wheel in isolated output directory")
            return 1
        verify_wheel(wheels[0])
        subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(root / "venv")], check=True
        )
        python = str(root / "venv/bin/python")
        packages = (
            root
            / "venv/lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
        (packages / "verification-dependencies.pth").write_text(
            sysconfig.get_path("purelib") + "\n"
        )
        code = run(
            [python, "-m", "pip", "install", "--no-deps", "--no-index", str(wheels[0].resolve())],
            directory / "wheel-install.log",
        )
        if code:
            return code
        script = (
            "from pathlib import Path; from importlib import resources; import hashlib; "
            "import azure_functions_validation as a; "
            f"assert Path(a.__file__).resolve().is_relative_to(Path({str(root)!r})); "
            "assert callable(a.validate_http); "
            "p=resources.files('azure_functions_validation.schemas'); "
            "assert hashlib.sha256(p.joinpath('endpoint.schema.json').read_bytes()).hexdigest() "
            "== p.joinpath('endpoint.schema.sha256').read_text().split()[0]; "
            "print('Installed wheel imports outside checkout; schema matches pin')"
        )
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
            result = subprocess.run(
                [python, "-I", "-c", script], cwd=root, stdout=output, stderr=subprocess.STDOUT
            )
            output.seek(0)
            text = redact(output.read())
        (directory / "wheel-smoke.log").write_text(text)
        print(text)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
