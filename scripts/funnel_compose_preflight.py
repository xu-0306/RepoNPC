"""Check the approved Compose baseline before resolving the Linux Funnel override."""

import re
import subprocess


def supported(version: str) -> bool:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-desktop\.\d+)?(?:\+\S+)?", version.strip())
    return match is not None and tuple(map(int, match.groups())) >= (2, 24, 4)


if __name__ == "__main__":
    try:
        version = subprocess.check_output(
            ["docker", "compose", "version", "--short"], text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        raise SystemExit("Docker Compose version could not be checked.") from None
    if not supported(version):
        raise SystemExit("Docker Compose 2.24.4 or later is required.")
    print("Docker Compose baseline passed; use the Funnel override on Linux only.")
