"""Installed RepoNPC command dispatch without unrelated startup side effects."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from reponpc.config.models import ConfigValidationError, load_public_config
from reponpc.indexing.pipeline import (
    IndexPipelineError,
    build_index_bundle,
    publish_index_bundle,
    publish_pending_manifest,
)
from reponpc.indexing.publication import PublicationError
from reponpc.main import run as run_server

_SAFE_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reponpc")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="start the RepoNPC web application")

    config = commands.add_parser("config", help="configuration commands")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    validate = config_commands.add_parser("validate", help="validate public configuration")
    validate.add_argument("path", type=Path)

    index = commands.add_parser("index", help="immutable index commands")
    index_commands = index.add_subparsers(dest="index_command", required=True)
    build = index_commands.add_parser("build", help="build and verify an immutable bundle")
    build.add_argument("--config", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    publish = index_commands.add_parser("publish", help="publish the immutable release asset")
    publish.add_argument("--bundle-dir", type=Path, required=True)
    publish_manifest = index_commands.add_parser(
        "publish-manifest", help="advance the stable manifest from a pending artifact"
    )
    publish_manifest.add_argument("--bundle-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        run_server()
        return 0
    args = _parser().parse_args(arguments)
    try:
        if args.command == "serve":
            run_server()
        elif args.command == "config":
            load_public_config(args.path)
            print("configuration valid")
        elif args.index_command == "build":
            bundle = build_index_bundle(args.config, args.output)
            print(f"bundle built: {bundle.manifest.bundle_id}")
        elif args.index_command == "publish":
            publish_index_bundle(args.bundle_dir)
            print("immutable bundle published; pending manifest recorded")
        else:
            publish_pending_manifest(args.bundle_dir)
            print("stable manifest published")
    except ConfigValidationError:
        print("reponpc: configuration_invalid", file=sys.stderr)
        return 2
    except (IndexPipelineError, PublicationError) as exc:
        print(f"reponpc: {exc.code}", file=sys.stderr)
        return 1
    except OSError:
        print("reponpc: operation_failed", file=sys.stderr)
        return 1
    except Exception as exc:
        candidate = getattr(exc, "code", None)
        code = (
            candidate
            if isinstance(candidate, str) and _SAFE_ERROR_CODE_RE.fullmatch(candidate)
            else "operation_failed"
        )
        print(f"reponpc: {code}", file=sys.stderr)
        return 1
    return 0


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
