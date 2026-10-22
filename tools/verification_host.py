"""Real validation host smoke with private Azurite storage and owned processes."""

from __future__ import annotations

import base64
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from tools.verification_process import child


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(process: subprocess.Popen[str], url: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("service exited before readiness")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except URLError:
            time.sleep(0.25)
    raise TimeoutError("service readiness deadline exceeded")


def host_smoke(directory: Path) -> int:
    directory = directory.resolve()
    suite = ET.Element("testsuite", name="real-functions-host")
    case = ET.SubElement(suite, "testcase", name="validated_context_and_response_filtering")
    try:
        with (
            tempfile.TemporaryDirectory(prefix="validation-host-") as temporary,
            ExitStack() as stack,
        ):
            work = Path(temporary)
            for name in ("function_app.py", "host.json"):
                (work / name).write_bytes((Path("tests/host_smoke") / name).read_bytes())
            blob, queue, table, port = (free_port() for _ in range(4))
            key = base64.b64encode(b"validation-local-emulator-only" * 2).decode()
            emulator = stack.enter_context(
                child(
                    [
                        "env",
                        f"AZURITE_ACCOUNTS=validationdev:{key}",
                        "azurite",
                        "--silent",
                        "--location",
                        str(work / "storage"),
                        "--blobPort",
                        str(blob),
                        "--queuePort",
                        str(queue),
                        "--tablePort",
                        str(table),
                    ],
                    directory / "logs/azurite.log",
                )
            )
            deadline = time.monotonic() + 30
            for service in (blob, queue, table):
                while True:
                    if emulator.poll() is not None or time.monotonic() >= deadline:
                        raise TimeoutError("Azurite failed readiness")
                    try:
                        with socket.create_connection(("127.0.0.1", service), timeout=1):
                            break
                    except OSError:
                        time.sleep(0.25)
            (work / "local.settings.json").write_text(
                json.dumps(
                    {
                        "IsEncrypted": False,
                        "Values": {
                            "FUNCTIONS_WORKER_RUNTIME": "python",
                            "AzureWebJobsStorage": (
                                f"DefaultEndpointsProtocol=http;AccountName=validationdev;AccountKey={key};"
                                f"BlobEndpoint=http://127.0.0.1:{blob}/validationdev;"
                                f"QueueEndpoint=http://127.0.0.1:{queue}/validationdev;"
                                f"TableEndpoint=http://127.0.0.1:{table}/validationdev;"
                            ),
                        },
                    }
                )
            )
            previous_path = os.environ.get("PATH", "")
            os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + previous_path
            try:
                host = stack.enter_context(
                    child(
                        ["func", "start", "--python", "--verbose", "--port", str(port)],
                        directory / "logs/host.log",
                        work,
                    )
                )
                url = f"http://127.0.0.1:{port}/api/smoke"
                wait_ready(host, url)
                with urlopen(url, timeout=5) as response:
                    assert json.load(response) == {"function_name": "smoke"}
            finally:
                os.environ["PATH"] = previous_path
        assert not re.search(
            r"0 functions (loaded|found \(Worker\))|No job functions found|"
            r"Executed 'Functions\..*' \(Failed",
            (directory / "logs/host.log").read_text(),
        )
        code = 0
    except (OSError, RuntimeError, TimeoutError, AssertionError, ValueError) as error:
        ET.SubElement(case, "failure").text = str(error)
        code = 1
    finally:
        destination = directory / "junit/junit.xml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(suite).write(destination, encoding="unicode")
    return code
