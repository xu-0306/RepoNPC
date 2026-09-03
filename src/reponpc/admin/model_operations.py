"""Bounded asynchronous operations for provider-owned Ollama model installs."""

from __future__ import annotations

import math
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from reponpc.admin.embedding_profiles import EmbeddingProfileError, EmbeddingProfileRegistry
from reponpc.providers.ollama_embeddings import OllamaPullCancelled


@dataclass(frozen=True, slots=True)
class OllamaModelOperation:
    operation_id: str
    profile_id: str
    model_id: str
    status: str
    completed: int | None
    total: int | None
    error_code: str | None
    updated_at: str


class OllamaModelOperationCoordinator:
    """Own one cancellable pull lane without persisting provider response bodies."""

    def __init__(self, registry: EmbeddingProfileRegistry) -> None:
        self._registry = registry
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ollama-pull")
        self._lock = threading.RLock()
        self._operations: dict[str, OllamaModelOperation] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}

    def queue_pull(self, profile_id: str, *, confirmed: bool) -> OllamaModelOperation:
        profile, operation = self._registry.prepare_ollama_model_action(
            profile_id, action="pull", confirmed=confirmed
        )
        with self._lock:
            if any(item.status in {"queued", "running"} for item in self._operations.values()):
                raise EmbeddingProfileError("EMBEDDING_MODEL_OPERATION_ACTIVE")
            operation_id = str(uuid.uuid4())
            snapshot = OllamaModelOperation(
                operation_id=operation_id,
                profile_id=profile.profile_id,
                model_id=profile.model_id,
                status="queued",
                completed=None,
                total=None,
                error_code=None,
                updated_at=_now(),
            )
            cancel = threading.Event()
            self._operations[operation_id] = snapshot
            self._cancel[operation_id] = cancel
            self._futures[operation_id] = self._executor.submit(
                self._run, operation_id, operation, cancel
            )
            return snapshot

    def get(self, operation_id: str) -> OllamaModelOperation:
        with self._lock:
            try:
                return self._operations[operation_id]
            except KeyError:
                raise EmbeddingProfileError("NOT_FOUND") from None

    def cancel(self, operation_id: str) -> OllamaModelOperation:
        with self._lock:
            snapshot = self.get(operation_id)
            if snapshot.status not in {"queued", "running"}:
                return snapshot
            cancel = self._cancel[operation_id]
            cancel.set()
            future = self._futures[operation_id]
            if future.cancel():
                self._set(operation_id, status="cancelled")
            return self._operations[operation_id]

    def shutdown(self) -> None:
        with self._lock:
            for operation_id, snapshot in self._operations.items():
                if snapshot.status in {"queued", "running"}:
                    self._cancel[operation_id].set()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _run(
        self,
        operation_id: str,
        operation: Callable[..., None],
        cancel: threading.Event,
    ) -> None:
        self._set(operation_id, status="running")

        def progress(completed: int | None, total: int | None) -> None:
            if completed is not None and (completed < 0 or not math.isfinite(completed)):
                return
            if total is not None and (total <= 0 or not math.isfinite(total)):
                return
            if completed is not None and total is not None and completed > total:
                return
            self._set(operation_id, completed=completed, total=total, update_progress=True)

        try:
            operation(cancelled=cancel.is_set, on_progress=progress)
            if cancel.is_set():
                raise OllamaPullCancelled
            snapshot = self.get(operation_id)
            self._registry.complete_ollama_model_action(
                snapshot.profile_id, action="pull", succeeded=True
            )
        except OllamaPullCancelled:
            self._set(operation_id, status="cancelled", error_code=None)
        except Exception:
            self._set(
                operation_id,
                status="failed",
                error_code="EMBEDDING_MODEL_OPERATION_FAILED",
            )
        else:
            self._set(operation_id, status="succeeded", error_code=None)

    def _set(
        self,
        operation_id: str,
        *,
        status: str | None = None,
        completed: int | None = None,
        total: int | None = None,
        error_code: str | None = None,
        update_progress: bool = False,
    ) -> None:
        with self._lock:
            current = self._operations.get(operation_id)
            if current is None or current.status in {"succeeded", "failed", "cancelled"}:
                return
            self._operations[operation_id] = OllamaModelOperation(
                operation_id=current.operation_id,
                profile_id=current.profile_id,
                model_id=current.model_id,
                status=status or current.status,
                completed=completed if update_progress else current.completed,
                total=total if update_progress else current.total,
                error_code=error_code,
                updated_at=_now(),
            )


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
