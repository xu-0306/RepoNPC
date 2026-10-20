"""The real FastAPI lifespan owns the polling lifecycle and safe status state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from reponpc.bundles.manager import BundleStatus
from reponpc.main import create_app
from reponpc.runtime.database import BundleRuntimeState, RuntimeDatabase


@dataclass
class LifecycleManager:
    active_bundle_id: str | None = "20260810T120000Z-0123456789ab"

    def status(self) -> BundleStatus:
        return BundleStatus(
            active_bundle_id=self.active_bundle_id,
            previous_bundle_id=None,
            pinned_bundle_id=None,
        )


class LifecycleUpdater:
    def __init__(self, runtime: RuntimeDatabase) -> None:
        self.runtime = runtime
        self.calls = 0

    def poll_once(self) -> str:
        self.calls += 1
        self.runtime.save_bundle_state(
            BundleRuntimeState(
                active_bundle_id="20260810T120000Z-0123456789ab",
                previous_bundle_id=None,
                pinned_bundle_id=None,
                manifest_etag='"fixture"',
                last_checked_at="2026-08-10T12:00:00Z",
                safe_update_error=None,
            )
        )
        return "activated"


def test_real_app_lifespan_polls_before_serving_and_stops_cleanly(tmp_path: Path) -> None:
    runtime = RuntimeDatabase(Path(tmp_path) / "runtime")
    manager = LifecycleManager()
    updater = LifecycleUpdater(runtime)
    application = create_app(
        runtime_database=runtime,
        bundle_manager=manager,  # type: ignore[arg-type]
        bundle_updater=updater,  # type: ignore[arg-type]
        bundle_poll_seconds=3600,
    )

    with TestClient(application) as client:
        response = client.get("/api/public/status")
        assert response.status_code == 200
        assert response.json()["index"] == {
            "ready": True,
            "version": "20260810T120000Z-0123456789ab",
            "last_checked_at": "2026-08-10T12:00:00Z",
            "update_error": None,
        }
        assert updater.calls == 1
    assert updater.calls == 1
