"""Frozen console entry point; importing this file starts no service."""

from __future__ import annotations


def main() -> int:
    from reponpc.windows_launcher import main as launch

    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
