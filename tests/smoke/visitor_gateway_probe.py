"""Run inside the built image: real loopback HTTP, synthetic data, no external calls."""

from __future__ import annotations

import asyncio
import json
import socket
import tempfile
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

from reponpc.api.public import SetupState
from reponpc.api.visitor_gateway import VisitorGateway, _LoopbackServer
from reponpc.config.environment import load_environment
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase


def get(port: int, path: str) -> tuple[int, bytes]:
    request = Request(f"http://127.0.0.1:{port}{path}", headers={"Host": "fixture.ts.net"})
    try:
        with urlopen(request, timeout=3) as response:
            assert "Set-Cookie" not in response.headers
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


async def probe() -> None:
    with tempfile.TemporaryDirectory(prefix="reponpc-a1-") as temporary:
        database = RuntimeDatabase(Path(temporary))
        database.initialize()
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        primary = create_app(
            setup_state=SetupState(
                index_ready=True,
                model_ready=True,
                index_version="fixture-bundle",
                model_provider="PRIVATE_MODEL_CANARY",
            )
        )
        private_socket = socket.socket()
        private_socket.bind(("127.0.0.1", 0))
        private_socket.listen()
        private_socket.setblocking(False)
        private_port = private_socket.getsockname()[1]
        assert private_socket.getsockname()[0] == "127.0.0.1" and private_port != port
        private_server = _LoopbackServer(
            uvicorn.Config(
                primary, lifespan="off", proxy_headers=False, log_config=None, access_log=False
            )
        )
        private_task = asyncio.create_task(private_server.serve(sockets=[private_socket]))
        environment = load_environment(
            {
                "REPONPC_PUBLIC_BASE_URL": "https://private.example.com",
                "REPONPC_ADMIN_ORIGINS": "https://private.example.com",
                "REPONPC_CONFIG_REPOSITORY": "example/fixture",
                "REPONPC_INDEX_MANIFEST_URL": "http://127.0.0.1:9/disabled",
                "REPONPC_VISITOR_GATEWAY_PORT": str(port),
                "REPONPC_PORT": str(private_port),
                "REPONPC_SHUTDOWN_GRACE_SECONDS": "1",
            }
        )
        gateway = VisitorGateway(
            database=database,
            environment=environment,
            state_supplier=lambda: primary.state.reponpc,
            bundle_manager_supplier=lambda: None,
            chat_service_supplier=lambda: None,
            faq_supplier=lambda: None,
            web_dist=Path("/app/apps/web/dist"),
        )
        configured = await gateway.configure(
            revision=1,
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
        )
        try:
            for _ in range(100):
                if private_server.started:
                    break
                await asyncio.sleep(0.01)
            assert private_server.started
            assert (await asyncio.to_thread(get, private_port, "/readyz"))[0] == 200
            started = await gateway.start(revision=configured["revision"])
            assert started["listener_ready"] and not started["external_verified"]
            code, body = await asyncio.to_thread(get, port, "/api/public/status")
            assert code == 200 and json.loads(body) == {
                "status": "ready",
                "chat_available": True,
                "index": {"ready": True, "version": "fixture-bundle"},
            }
            assert b"PRIVATE_" not in body
            assert gateway._socket.getsockname()[0] == "127.0.0.1"
            primary.state.reponpc = replace(primary.state.reponpc, model_ready=False)
            for listener_port in (private_port, port):
                assert (await asyncio.to_thread(get, listener_port, "/readyz"))[0] == 503
            primary.state.reponpc = replace(primary.state.reponpc, model_ready=True)
            assert (await asyncio.to_thread(get, port, "/"))[0] == 200
            for path in ("/admin", "/api/admin/setup", "/openapi.json", "/unknown"):
                assert (await asyncio.to_thread(get, port, path))[0] == 404
            manifest = json.loads(Path("/app/apps/web/dist/.vite/manifest.json").read_bytes())
            for entry in manifest.values():
                if entry.get("isDynamicEntry"):
                    assert (await asyncio.to_thread(get, port, "/" + entry["file"]))[0] == 404
            stopped = await gateway.stop(revision=started["revision"])
            assert not stopped["listener_ready"] and not stopped["enabled"]
        finally:
            await gateway.shutdown()
            private_server.should_exit = True
            await asyncio.wait_for(private_task, timeout=3)
            private_socket.close()
    print("A1 image loopback gateway: status, manifest, private-path denial and stop passed")


if __name__ == "__main__":
    asyncio.run(probe())
