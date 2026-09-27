"""Synthetic production-stack fixture for the AC-077 browser check.

This fixture reuses the existing isolated analysis harness, then seeds one
terminal batch with both a retryable failure and a successful item that can be
reanalyzed.  The browser still talks to the real authenticated FastAPI routes;
the only external transports are the deterministic fixtures from the shared
harness.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import uvicorn
from analysis_recovery_server import build_application

from reponpc.admin.batch_resolver import RepositorySelection
from reponpc.admin.batch_runtime import TERMINAL_BATCH_STATES
from reponpc.admin.batches import BatchPreflightInput


def seed_recoverable_batch(application: object) -> str:
    """Create and finish a deterministic batch before serving the browser."""

    batches = application.batches  # type: ignore[attr-defined]
    controller = application.chat_controller  # type: ignore[attr-defined]
    controller.retry_release.set()
    selections = (
        RepositorySelection("fixture/alpha"),
        RepositorySelection("fixture/fails-once"),
    )
    plan = batches.preflight(BatchPreflightInput(selections))
    snapshot, created = batches.create(
        plan_id=plan.plan_id,
        selections=selections,
        idempotency_key="r11-browser-seed",
    )
    if not created:
        raise RuntimeError("R11 fixture seed unexpectedly reused a batch")

    deadline = time.monotonic() + 60
    while snapshot.state not in TERMINAL_BATCH_STATES:
        if time.monotonic() >= deadline:
            raise RuntimeError("R11 fixture seed did not reach a terminal state")
        time.sleep(0.05)
        snapshot = batches.get(snapshot.batch_id)

    if not any(item.retryable or item.reanalyzable for item in snapshot.items):
        raise RuntimeError("R11 fixture seed is not actionable")
    if not any(item.retryable for item in snapshot.items):
        raise RuntimeError("R11 fixture seed has no retryable item")
    if not any(item.reanalyzable for item in snapshot.items):
        snapshot = batches.action(snapshot.batch_id, action="retry")
        while snapshot.state not in TERMINAL_BATCH_STATES:
            if time.monotonic() >= deadline:
                raise RuntimeError("R11 fixture retry did not reach a terminal state")
            time.sleep(0.05)
            snapshot = batches.get(snapshot.batch_id)
    if not any(item.reanalyzable for item in snapshot.items):
        raise RuntimeError("R11 fixture seed has no reanalyzable item")
    return snapshot.batch_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--web-dist", type=Path, default=Path("apps/web/dist"))
    parser.add_argument("--port", type=int, default=8777)
    args = parser.parse_args()

    origin = f"http://127.0.0.1:{args.port}"
    application, grant = build_application(
        args.runtime,
        args.web_dist.resolve(),
        origin,
    )
    batch_id = seed_recoverable_batch(application)
    print(f"R11_SEEDED_BATCH={batch_id}", flush=True)
    print(f"BROWSER_URL={origin}/admin#local-launch={grant}", flush=True)
    uvicorn.run(application, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
