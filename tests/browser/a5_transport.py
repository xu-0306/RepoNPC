"""Loopback transport for the unmodified production static-site controller.

The test service worker maps only the fixture HTTPS gateway to a real loopback
listener. It supplies no responses; stopping that listener causes real failures.
This does not establish public TLS, GitHub Pages or Funnel acceptance.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

GATEWAY_ORIGIN = "https://fixture.ts.net"
PAGES_ORIGIN = "https://fixture.github.io"


class GatewayFixtureTransport:
    """Map the two exact test authorities around the real gateway ASGI app."""

    def __init__(self, application: Any, *, gateway_port: int, static_origin: str) -> None:
        self.application = application
        self.authority = f"127.0.0.1:{gateway_port}".encode("ascii")
        self.static_origin = static_origin.encode("ascii")
        self.requests = 0

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return
        headers = scope.get("headers", [])
        hosts = [value for key, value in headers if key.lower() == b"host"]
        origins = [value for key, value in headers if key.lower() == b"origin"]
        mapped = hosts == [self.authority] and origins == [self.static_origin]
        if mapped:
            scope = {
                **scope,
                "scheme": "https",
                "headers": [
                    (
                        key,
                        b"fixture.ts.net"
                        if key.lower() == b"host"
                        else PAGES_ORIGIN.encode("ascii")
                        if key.lower() == b"origin"
                        else value,
                    )
                    for key, value in headers
                ],
            }
            self.requests += 1

        async def local_cors(message: dict[str, Any]) -> None:
            if mapped and message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        (
                            key,
                            self.static_origin
                            if key.lower() == b"access-control-allow-origin"
                            and value == PAGES_ORIGIN.encode("ascii")
                            else value,
                        )
                        for key, value in message["headers"]
                    ],
                }
            await send(message)

        await self.application(scope, receive, local_cors)


def static_server(
    *, site: Path, base_path: str, port: int, gateway_port: int, audit_script: Path | None = None
) -> ThreadingHTTPServer:
    """Serve only a verified export tree and explicitly named test controls."""

    site = site.resolve(strict=True)
    if not site.is_dir() or not (site / "export-manifest.json").is_file():
        raise ValueError("a completed static export is required")
    if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)?", base_path):
        raise ValueError("fixture base path must be root or one project segment")
    config = json.dumps({"basePath": base_path, "gateway": f"http://127.0.0.1:{gateway_port}"})
    worker = (
        "const fixture = "
        + config
        + ";\n"
        + r"""
self.addEventListener('install', (event) => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== 'https://fixture.ts.net') return;
  event.respondWith((async () => {
    if (request.credentials !== 'omit') throw new Error('Fixture requires credentials omit');
    const target = fixture.gateway + url.pathname + url.search;
    const headers = new Headers();
    for (const name of ['accept', 'content-type']) {
      if (request.headers.has(name)) headers.set(name, request.headers.get(name));
    }
    const response = await fetch(target, {
      method: request.method, headers, credentials: 'omit', mode: 'cors',
      cache: 'no-store', redirect: 'error', signal: request.signal,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(),
    });
    // Do not expose the mapped response URL to the page's production CSP.
    return new Response(response.body, {
      status: response.status, statusText: response.statusText, headers: response.headers,
    });
  })());
});
"""
    ).encode("utf-8")
    start_script = (
        "const fixture = "
        + config
        + ";\n"
        + r"""
document.querySelector('button').addEventListener('click', async () => {
  const output = document.querySelector('output');
  try {
    await navigator.serviceWorker.register('/__a5-test/transport.js', {scope: '/'});
    await navigator.serviceWorker.ready;
    output.textContent = 'Fixture transport ready';
    const link = document.querySelector('a');
    link.href = fixture.basePath;
    link.hidden = false;
  } catch (error) { output.textContent = String(error); }
});
document.querySelector('[data-disconnect]').addEventListener('click', async () => {
  const registration = await navigator.serviceWorker.getRegistration('/');
  if (registration) await registration.unregister();
  document.querySelector('output').textContent = 'Fixture transport disconnected';
});
document.querySelector('[data-check]').addEventListener('click', async () => {
  const output = document.querySelector('output');
  try {
    const response = await fetch('https://fixture.ts.net/api/public/status', {credentials: 'omit'});
    const body = await response.json();
    output.textContent = 'Fixture gateway ' + response.status + ': ' + body.status;
  } catch { output.textContent = 'Fixture gateway unavailable'; }
});
"""
    ).encode("utf-8")
    start_document = b"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>A5 static browser fixture</title><script src="/__a5-test/start.js" defer></script>
</head><body><main><h1>A5 static browser fixture</h1>
<button type="button">Connect fixture transport</button><output aria-live="polite"></output>
<button type="button" data-disconnect>Disconnect fixture transport</button>
<button type="button" data-check>Check fixture gateway</button>
<a href="/" hidden>Open exported site</a></main></body></html>"""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._serve(head=False)

        def do_HEAD(self) -> None:
            self._serve(head=True)

        def _serve(self, *, head: bool) -> None:
            path = unquote(urlsplit(self.path).path)
            helpers = {
                "/__a5-test/start": (start_document, "text/html"),
                "/__a5-test/start.js": (start_script, "text/javascript"),
                "/__a5-test/transport.js": (worker, "text/javascript"),
            }
            if audit_script is not None:
                helpers["/__a5-test/axe.js"] = (audit_script.read_bytes(), "text/javascript")
                helpers["/__a5-test/acceptance.js"] = (
                    Path(__file__).with_name("a5-acceptance.js").read_bytes(),
                    "text/javascript",
                )
            if path in helpers:
                content, media = helpers[path]
            else:
                if not path.startswith(base_path) or "\\" in path or "\x00" in path:
                    self.send_error(404)
                    return
                relative = path.removeprefix(base_path) or "index.html"
                if any(part in {"", ".", ".."} for part in relative.split("/")):
                    self.send_error(404)
                    return
                target = site / relative
                if (
                    not target.resolve().is_relative_to(site)
                    or target.is_symlink()
                    or not target.is_file()
                ):
                    self.send_error(404)
                    return
                content = target.read_bytes()
                media = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if media == "text/html" and audit_script is not None:
                    from tests.browser.a5_server import acceptance_document

                    content = acceptance_document(content)
            self.send_response(200)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if path == "/__a5-test/transport.js":
                self.send_header("Service-Worker-Allowed", "/")
            self.end_headers()
            if not head:
                self.wfile.write(content)

        def log_message(self, _format: str, *args: object) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--base-path", default="/")
    parser.add_argument("--port", type=int, default=8781)
    parser.add_argument("--gateway-port", type=int, default=8782)
    parser.add_argument("--axe-script", type=Path)
    args = parser.parse_args()
    with static_server(
        site=args.site,
        base_path=args.base_path,
        port=args.port,
        gateway_port=args.gateway_port,
        audit_script=args.axe_script,
    ) as server:
        print(f"BROWSER_URL=http://127.0.0.1:{args.port}/__a5-test/start", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
