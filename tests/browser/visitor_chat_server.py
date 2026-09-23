"""Production-stack visitor chat acceptance server for R09/R14.

The real built React application and public FastAPI routes stay in the path.
Only the external chat-answer boundary is deterministic. Test-only controls
publish secret-free request metadata and allow safe status/barrier changes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import threading
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import uvicorn
from starlette.responses import JSONResponse

from reponpc.api.public import SetupState
from reponpc.chat.answers import Citation
from reponpc.chat.service import ChatDelivery, ChatHistoryMessage
from reponpc.main import create_app


def _content_id(value: str) -> str:
    if value.startswith("Validated answer for ") and value.endswith(". [S1]"):
        return "answer:" + value.removeprefix("Validated answer for ").removesuffix(". [S1]")
    if value and set(value) == {"長"}:
        return "long-answer"
    return "question:" + value


class VisitorChatController:
    def __init__(self, runtime_id: str) -> None:
        self.runtime_id = runtime_id
        self.calls: list[dict[str, object]] = []
        self.attempts: Counter[str] = Counter()
        self.release = threading.Event()
        self.disconnect_observed = False
        self.transport_mode = "normal"
        self._lock = threading.Lock()

    def record(
        self,
        message: str,
        locale: str,
        history: tuple[ChatHistoryMessage, ...],
    ) -> int:
        with self._lock:
            self.attempts[message] += 1
            attempt = self.attempts[message]
            self.transport_mode = (
                "incomplete"
                if message == "browser-incomplete"
                else "paced"
                if message == "browser-normal"
                else "normal"
            )
            self.calls.append(
                {
                    "message_id": _content_id(message),
                    "locale": locale,
                    "attempt": attempt,
                    "history": [
                        {
                            "role": item.role,
                            "content_id": _content_id(item.content),
                            "code_points": len(item.content),
                            "sha256": hashlib.sha256(item.content.encode()).hexdigest(),
                        }
                        for item in history
                    ],
                }
            )
            return attempt

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "runtime_id": self.runtime_id,
                "calls": list(self.calls),
                "attempts": dict(self.attempts),
                "disconnect_observed": self.disconnect_observed,
            }


class FixtureVisitorChatService:
    timeout_seconds = 30.0

    def __init__(self, controller: VisitorChatController) -> None:
        self.controller = controller

    def answer(
        self,
        *,
        message: str,
        locale: str,
        history: tuple[ChatHistoryMessage, ...],
        client_ip: str,
        cancel_requested: threading.Event | None = None,
    ) -> ChatDelivery:
        del client_ip
        attempt = self.controller.record(message, locale, history)
        if message == "browser-failure" and attempt == 1:
            raise RuntimeError("deterministic prestream failure")
        if message == "browser-failure-delayed":
            self.controller.release.wait(timeout=20)
            self.controller.release.clear()
            raise RuntimeError("deterministic delayed failure")
        if message in {"browser-normal", "browser-double"}:
            self.controller.release.wait(timeout=20)
            self.controller.release.clear()
        if message == "browser-unmount":
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if cancel_requested is not None and cancel_requested.is_set():
                    with self.controller._lock:
                        self.controller.disconnect_observed = True
                    raise RuntimeError("client disconnected")
                time.sleep(0.01)
            raise TimeoutError
        answer = (
            "長" * 4001 if message == "browser-long" else f"Validated answer for {message}. [S1]"
        )
        citation = Citation(
            "S1",
            "E_" + "a" * 24,
            "REPOSITORY_FACT",
            "fixture-owner/reponpc-demo",
            "b" * 40,
            "src/main.py",
            10,
            12,
            "Fixture evidence",
            "Validated fixture excerpt",
            "https://github.com/fixture-owner/reponpc-demo/blob/"
            + "b" * 40
            + "/src/main.py#L10-L12",
        )
        return ChatDelivery(
            "browser-fixture-v1",
            locale,  # type: ignore[arg-type]
            1,
            answer,
            (citation,),
            "stop",
            None,
            False,
        )


class VisitorAcceptanceApp:
    def __init__(self, application: Any, controller: VisitorChatController) -> None:
        self.application = application
        self.controller = controller

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return
        path = str(scope["path"])
        method = str(scope["method"])
        if path == "/__visitor-test/state":
            payload = self.controller.snapshot()
            payload["chat_available"] = self.application.state.reponpc.ready
            await JSONResponse(payload)(scope, receive, send)
            return
        if method == "POST" and path == "/__visitor-test/release":
            self.controller.release.set()
            await JSONResponse({"ok": True})(scope, receive, send)
            return
        if method == "POST" and path in {
            "/__visitor-test/status/ready",
            "/__visitor-test/status/unavailable",
        }:
            ready = path.endswith("/ready")
            self.application.state.reponpc = replace(
                self.application.state.reponpc,
                model_ready=ready,
            )
            await JSONResponse({"chat_available": ready})(scope, receive, send)
            return
        if method == "POST" and path == "/api/public/chat/stream":
            token_seen = False
            pause_applied = False

            async def controlled_send(message: dict[str, Any]) -> None:
                nonlocal pause_applied, token_seen
                if message["type"] != "http.response.body":
                    await send(message)
                    return
                payload = bytes(message.get("body", b""))
                if b"event: token" in payload:
                    token_seen = True
                    await send(message)
                    return
                incomplete = self.controller.transport_mode == "incomplete"
                paced = self.controller.transport_mode == "paced"
                if paced and token_seen and not pause_applied:
                    pause_applied = True
                    await asyncio.sleep(1.5)
                if incomplete and token_seen and message.get("more_body", False):
                    return
                if incomplete and token_seen:
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                    return
                await send(message)

            await self.application(scope, receive, controlled_send)
            return
        await self.application(scope, receive, send)


def _write_public_bundle(runtime_root: Path) -> Path:
    public = runtime_root / "public"
    public.mkdir(parents=True)
    locales = {
        "zh-TW": {
            "profile": {
                "display_name": "Browser Acceptance Developer",
                "headline": "繁體中文標題",
                "bio": "繁體中文簡介",
                "greeting": "繁體中文問候",
                "location": None,
                "avatar_url": None,
                "links": [],
            },
            "repositories": [
                {
                    "slug": "fixture-owner/reponpc-demo",
                    "summary": "繁體中文專案摘要",
                    "role": "繁體中文角色",
                    "tags": ["Python"],
                    "demo_url": None,
                }
            ],
            "suggested_questions": ["繁體中文建議問題?"],
        },
        "en": {
            "profile": {
                "display_name": "Browser Acceptance Developer",
                "headline": "English headline",
                "bio": "English bio",
                "greeting": "English greeting",
                "location": None,
                "avatar_url": None,
                "links": [],
            },
            "repositories": [
                {
                    "slug": "fixture-owner/reponpc-demo",
                    "summary": "English project summary",
                    "role": "English role",
                    "tags": ["Python"],
                    "demo_url": None,
                }
            ],
            "suggested_questions": ["English suggested question?"],
        },
    }
    profile = {
        "schema_version": 1,
        "locales": locales,
        "character": {
            "mode": "builtin",
            "asset_url": "/api/public/character.png",
            "revision": 7,
            "frame_duration_ms": 240,
            "movement": "subtle",
        },
        "index": {
            "version": "browser-fixture-v1",
            "built_at": "2026-09-19T00:00:00Z",
            "repository_count": 1,
        },
    }
    (public / "profile.json").write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    source_image = Path(__file__).resolve().parents[2] / "reponpc-how-it-works.png"
    shutil.copyfile(source_image, public / "character.png")
    return public


def _isolated_web_dist(runtime_root: Path, web_dist: Path) -> Path:
    isolated = runtime_root / "web-dist"
    shutil.copytree(web_dist, isolated)
    index_path = isolated / "index.html"
    index_path.write_text(
        index_path.read_text(encoding="utf-8").replace(
            "<head>", '<head><script src="/visitor-acceptance.js"></script>', 1
        ),
        encoding="utf-8",
    )
    (isolated / "visitor-acceptance.js").write_text(
        r"""
if (new URLSearchParams(location.search).get('reduced') === '1') {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => query === '(prefers-reduced-motion: reduce)'
    ? {matches: true, media: query, onchange: null, addListener() {}, removeListener() {},
       addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; }}
    : original(query);
}
document.documentElement.dataset.browserUserAgent = navigator.userAgent;
window.addEventListener('DOMContentLoaded', () => {
  const controls = document.createElement('section');
  controls.setAttribute('aria-label', 'Visitor acceptance controls');
  controls.innerHTML = `<details open><summary>Visitor acceptance controls</summary>
    <button type="button" data-action="refresh">Refresh visitor state</button>
    <button type="button" data-action="release">Release blocked chat</button>
    <button type="button" data-action="ready">Set status ready</button>
    <button type="button" data-action="unavailable">Set status unavailable</button>
    <button type="button" data-action="reset-transitions">Reset character transitions</button>
    <pre data-visitor-state>{}</pre>
    <pre data-character-transitions>[]</pre></details>`;
  document.body.append(controls);
  const transitionOutput = controls.querySelector('[data-character-transitions]');
  const recordTransition = () => {
    const state = document.querySelector('[data-character-state]')?.dataset.characterState;
    const values = JSON.parse(transitionOutput.textContent || '[]');
    if (state && values.at(-1) !== state) {
      values.push(state);
      transitionOutput.textContent = JSON.stringify(values);
    }
  };
  const stateObserver = new MutationObserver(recordTransition);
  stateObserver.observe(document.body, {
    attributes: true,
    attributeFilter: ['data-character-state'],
    childList: true,
    subtree: true,
  });
  recordTransition();
  const refresh = async () => {
    const response = await fetch('/__visitor-test/state');
    controls.querySelector('[data-visitor-state]').textContent =
      JSON.stringify(await response.json(), null, 2);
    controls.dataset.stateVersion = String(Number(controls.dataset.stateVersion || '0') + 1);
  };
  controls.addEventListener('click', (event) => {
    const action = event.target?.dataset?.action;
    if (action === 'refresh') void refresh();
    if (action === 'release') void fetch('/__visitor-test/release', {method: 'POST'}).then(refresh);
    if (action === 'ready') {
      void fetch('/__visitor-test/status/ready', {method: 'POST'}).then(refresh);
    }
    if (action === 'unavailable') {
      void fetch('/__visitor-test/status/unavailable', {method: 'POST'}).then(refresh);
    }
    if (action === 'reset-transitions') {
      transitionOutput.textContent = '[]';
      recordTransition();
    }
  });
});
""".strip(),
        encoding="utf-8",
    )
    return isolated


def build_application(runtime_root: Path, web_dist: Path):
    runtime_id = runtime_root.name
    public = _write_public_bundle(runtime_root)
    isolated_web = _isolated_web_dist(runtime_root, web_dist)
    controller = VisitorChatController(runtime_id)
    state = SetupState(
        index_ready=True,
        index_version="browser-fixture-v1",
        index_last_checked_at="2026-09-19T00:00:00Z",
        model_ready=True,
        model_provider="ollama",
        model_last_checked_at="2026-09-19T00:00:00Z",
        public_directory=public,
    )
    application = create_app(
        setup_state=state,
        chat_service=FixtureVisitorChatService(controller),  # type: ignore[arg-type]
        max_message_characters=4000,
        max_history_messages=10,
        max_history_characters=12000,
        web_dist=isolated_web,
    )
    return VisitorAcceptanceApp(application, controller)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--web-dist", type=Path, default=Path("apps/web/dist"))
    parser.add_argument("--port", type=int, default=8771)
    args = parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=True)
    application = build_application(args.runtime, args.web_dist.resolve())
    print(f"BROWSER_URL=http://127.0.0.1:{args.port}/", flush=True)
    uvicorn.run(application, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
