"""Disposable loopback admin with an editable scripted Tailscale state.

From the repository root, with a fresh disposable runtime directory:

    .venv/Scripts/python.exe -m tests.browser.tailscale_server \
        --runtime .tmp/ts-r2/browser-b1 --port 8881 --gateway-port 8882 \
        --fake-tailscale-state-file .tmp/ts-r2/tailscale-state.json

The state file is initialized from tests/fixtures/tailscale/ready.json if absent.
Edit its status/serve JSON between clicks; the runner reloads on EVERY call.
Set installed=false for not_installed, or failure to timeout/invalid_json/oversize
for error. Start/off update this same synthetic JSON. No real CLI is invoked.
Use the printed fragment-only local-launch URL within two minutes. Save the Pages
URL in the UI, or pass --pages-url https://fixture.github.io/project/ to prefill.
The existing apps/web/dist is served; building the web app belongs to worker B2.
Ctrl+C stops the host and its visitor listener. Only ports 8881-8883 are accepted.
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

import uvicorn

from reponpc.admin.auth import AdminSessionService, issue_admin_local_launch_grant
from reponpc.api.visitor_gateway import VisitorGateway
from reponpc.config.environment import load_environment
from reponpc.sharing.pages import PagesSharingService
from reponpc.tailscale.service import TailscaleFunnelService
from tests.browser.a5_server import A5AcceptanceApp, build_application
from tests.support.fake_tailscale import FakeTailscaleRunner, fixture_state

FIXTURE_PORTS = (8881, 8882, 8883)


def build_tailscale_application(
    runtime: Path,
    web_dist: Path,
    state_file: Path,
    *,
    port: int = 8881,
    gateway_port: int = 8882,
    pages_url: str | None = None,
) -> tuple[A5AcceptanceApp, str]:
    if port not in FIXTURE_PORTS or gateway_port not in FIXTURE_PORTS or port == gateway_port:
        raise ValueError("Use two different fixture ports from 8881, 8882, 8883.")
    if not state_file.exists():
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(fixture_state(), indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    origin = f"http://127.0.0.1:{port}"
    fixture = build_application(runtime, web_dist, origin)
    app = fixture.application
    database = app.state.runtime_database
    environment = load_environment(
        {
            "REPONPC_DEPLOYMENT_PROFILE": "loopback_evaluation",
            "REPONPC_HOST": "127.0.0.1",
            "REPONPC_PORT": str(port),
            "REPONPC_PUBLIC_BASE_URL": origin,
            "REPONPC_ADMIN_ORIGINS": origin,
            "REPONPC_TRUSTED_HOSTS": "127.0.0.1,localhost",
            "REPONPC_VISITOR_GATEWAY_PORT": str(gateway_port),
            "REPONPC_SHUTDOWN_GRACE_SECONDS": "1",
        }
    )
    app.state.deployment_profile = environment.deployment_profile
    app.state.trusted_hosts = environment.trusted_hosts
    app.state.admin_session_service = AdminSessionService(
        database=database,
        deployment_profile="loopback_evaluation",
        identity_hmac_key=secrets.token_bytes(32),
    )
    gateway = VisitorGateway(
        database=database,
        environment=environment,
        state_supplier=lambda: app.state.reponpc,
        bundle_manager_supplier=lambda: app.state.bundle_manager,
        chat_service_supplier=lambda: app.state.chat_service,
        faq_supplier=app.state.faq_supplier,
        scene_supplier=app.state.scene_supplier,
        web_dist=web_dist,
    )
    app.state.visitor_gateway = gateway
    pages = PagesSharingService(
        database=database,
        faq=app.state.faq_supplier(),
        scene_service=app.state.scene_supplier(),
        gateway_supplier=lambda: gateway,
    )
    if pages_url is not None:
        pages.configure_pages(pages_url=pages_url)

    def pages_origin() -> str | None:
        saved = pages.state()["pages_origin"]
        return saved if isinstance(saved, str) else None

    def executable() -> str | None:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return "/synthetic/tailscale.exe" if data.get("installed", True) else None

    app.state.tailscale_service = TailscaleFunnelService(
        profile="loopback_evaluation",
        gateway=gateway,
        pages_origin_supplier=pages_origin,
        runner=FakeTailscaleRunner(state_file=state_file),
        executable_supplier=executable,
    )
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    return fixture, f"{origin}/admin#local-launch={grant}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--web-dist", type=Path, default=Path("apps/web/dist"))
    parser.add_argument("--port", type=int, choices=FIXTURE_PORTS, default=8881)
    parser.add_argument("--gateway-port", type=int, choices=FIXTURE_PORTS, default=8882)
    parser.add_argument("--fake-tailscale-state-file", type=Path, required=True)
    parser.add_argument("--pages-url")
    args = parser.parse_args()
    if args.port == args.gateway_port:
        parser.error("--port and --gateway-port must differ")
    fixture, launch_url = build_tailscale_application(
        args.runtime.resolve(),
        args.web_dist.resolve(),
        args.fake_tailscale_state_file.resolve(),
        port=args.port,
        gateway_port=args.gateway_port,
        pages_url=args.pages_url,
    )
    print(f"BROWSER_URL={launch_url}", flush=True)
    uvicorn.run(fixture, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
