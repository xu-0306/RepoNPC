"""Atomic bundle activation with in-flight read handles and retained rollback."""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from reponpc.bundles.archive import VerifiedBundle, verify_retained_bundle_directory
from reponpc.bundles.index_reader import ReadOnlyIndex
from reponpc.bundles.manifest import BundleManifest
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import BundleRuntimeState, RuntimeDatabase


class BundleActivationError(RuntimeError):
    """A safe activation error that does not expose local candidate paths."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("bundle activation failed")


@dataclass(frozen=True, slots=True)
class ActivationTransition:
    """Rollback/commit hooks for one durable cross-owner activation intent."""

    rollback: Callable[[], None]
    commit: Callable[[], None]


@dataclass(slots=True)
class _LiveBundle:
    directory: Path
    manifest: BundleManifest
    index: ReadOnlyIndex
    leases: int = 0
    retired: bool = False


@dataclass(frozen=True, slots=True)
class BundleStatus:
    """Safe bundle status consumed by readiness/status layers."""

    active_bundle_id: str | None
    previous_bundle_id: str | None
    pinned_bundle_id: str | None


class BundleManager:
    """One-process immutable-handle owner with atomic pointer replacement."""

    def __init__(
        self,
        *,
        data_directory: Path,
        runtime_database: RuntimeDatabase,
        expected_embedding: EmbeddingIdentity,
        keep_valid_bundles: int = 2,
    ) -> None:
        if keep_valid_bundles < 2:
            raise ValueError("at least active and previous bundles must be retained")
        self._root = Path(data_directory) / "bundles"
        self._bundles = self._root / "validated"
        self._pointer = self._root / "active.json"
        self._runtime = runtime_database
        self._embedding = expected_embedding
        self._keep = keep_valid_bundles
        self._lock = threading.RLock()
        self._active: _LiveBundle | None = None
        self._previous: _LiveBundle | None = None
        state = runtime_database.bundle_state()
        self._pinned: str | None = state.pinned_bundle_id
        self._root.mkdir(parents=True, exist_ok=True)
        self._bundles.mkdir(parents=True, exist_ok=True)
        self._restore_persisted_bundles(state)

    @contextmanager
    def acquire(self) -> Iterator[ReadOnlyIndex]:
        """Lease the current reader so an activation cannot close it in flight."""

        with self._lock:
            if self._active is None:
                raise BundleActivationError("bundle_unavailable")
            current = self._active
            current.leases += 1
        try:
            yield current.index
        finally:
            with self._lock:
                current.leases -= 1
                self._close_if_retired(current)

    def activate(
        self,
        candidate: VerifiedBundle,
        *,
        before_pointer_swap: Callable[[], None] | None = None,
        expected_embedding: EmbeddingIdentity | None = None,
        state_transition: Callable[[], ActivationTransition | Callable[[], None] | None]
        | None = None,
    ) -> BundleStatus:
        """Promote a fully verified staged candidate in one pointer transition."""

        with self._lock:
            selected_embedding = expected_embedding or self._embedding
            if candidate.manifest.embedding != selected_embedding:
                candidate.close()
                shutil.rmtree(candidate.directory, ignore_errors=True)
                raise BundleActivationError("bundle_embedding_incompatible")
            if self._pinned is not None and candidate.manifest.bundle_id != self._pinned:
                candidate.close()
                shutil.rmtree(candidate.directory, ignore_errors=True)
                raise BundleActivationError("bundle_pinned")
            if self._active and candidate.manifest.bundle_id == self._active.manifest.bundle_id:
                candidate.close()
                shutil.rmtree(candidate.directory, ignore_errors=True)
                return self.status()
            final_directory = self._bundles / candidate.manifest.bundle_id
            if final_directory.exists():
                candidate.close()
                shutil.rmtree(candidate.directory, ignore_errors=True)
                raise BundleActivationError("bundle_id_already_present")
            candidate.close()
            transition_hooks: ActivationTransition | Callable[[], None] | None = None
            try:
                os.replace(candidate.directory, final_directory)
                index = ReadOnlyIndex.open(
                    final_directory / "index.sqlite", expected_embedding=selected_embedding
                )
                promoted = _LiveBundle(final_directory, candidate.manifest, index)
                if before_pointer_swap is not None:
                    before_pointer_swap()
                if state_transition is not None:
                    transition_hooks = state_transition()
                self._write_pointer(candidate.manifest.bundle_id)
            except Exception as exc:
                _run_rollback(transition_hooks)
                if "index" in locals():
                    index.close()
                shutil.rmtree(final_directory, ignore_errors=True)
                raise BundleActivationError("bundle_pointer_swap_failed") from exc
            old_active = self._active
            old_previous = self._previous
            old_active_retired = old_active.retired if old_active is not None else False
            old_previous_retired = old_previous.retired if old_previous is not None else False
            old_embedding = self._embedding
            self._active = promoted
            self._previous = old_active
            self._embedding = selected_embedding
            if old_active is not None:
                old_active.retired = True
            if old_previous is not None and old_previous is not old_active:
                old_previous.retired = True
            try:
                self._persist_state()
                if isinstance(transition_hooks, ActivationTransition):
                    transition_hooks.commit()
            except Exception as exc:
                self._active = old_active
                self._previous = old_previous
                self._embedding = old_embedding
                if old_active is not None:
                    old_active.retired = old_active_retired
                if old_previous is not None:
                    old_previous.retired = old_previous_retired
                with suppress(Exception):
                    self._persist_state()
                self._fail_closed_restore_pointer(
                    old_active.manifest.bundle_id if old_active else None
                )
                _run_rollback(transition_hooks)
                promoted.index.close()
                shutil.rmtree(final_directory, ignore_errors=True)
                raise BundleActivationError("bundle_pointer_swap_failed") from exc
            if old_active is not None:
                self._close_if_retired(old_active)
            if old_previous is not None and old_previous is not old_active:
                self._close_if_retired(old_previous)
            self._cleanup_unreferenced()
            return self.status()

    def pin(self, bundle_id: str) -> BundleStatus:
        """Select a retained compatible local bundle as the active bundle."""

        with self._lock:
            if not bundle_id or bundle_id not in self._retained_ids():
                raise BundleActivationError("bundle_pin_target_unknown")
            previous_pin = self._pinned
            if self._active is not None and self._active.manifest.bundle_id == bundle_id:
                self._pinned = bundle_id
                try:
                    self._persist_state()
                except Exception as exc:
                    self._pinned = previous_pin
                    raise BundleActivationError("bundle_pin_target_incompatible") from exc
                return self.status()

            promoted = self._open_retained(bundle_id)
            if promoted is None:
                raise BundleActivationError("bundle_pin_target_incompatible")
            old_active = self._active
            old_previous = self._previous
            old_active_retired = old_active.retired if old_active is not None else False
            old_previous_retired = old_previous.retired if old_previous is not None else False
            try:
                self._write_pointer(bundle_id)
                self._active = promoted
                self._previous = old_active
                self._pinned = bundle_id
                self._persist_state()
            except Exception as exc:
                self._active = old_active
                self._previous = old_previous
                self._pinned = previous_pin
                if old_active is not None:
                    old_active.retired = old_active_retired
                if old_previous is not None:
                    old_previous.retired = old_previous_retired
                self._fail_closed_restore_pointer(
                    old_active.manifest.bundle_id if old_active else None
                )
                promoted.index.close()
                raise BundleActivationError("bundle_pin_target_incompatible") from exc
            if old_active is not None:
                old_active.retired = True
                self._close_if_retired(old_active)
            if old_previous is not None and old_previous is not old_active:
                old_previous.retired = True
                self._close_if_retired(old_previous)
            return self.status()

    def unpin(self) -> BundleStatus:
        """Resume normal polling without mutating any immutable bundle."""

        with self._lock:
            previous_pin = self._pinned
            self._pinned = None
            try:
                self._persist_state()
            except Exception as exc:
                self._pinned = previous_pin
                raise BundleActivationError("bundle_pin_target_incompatible") from exc
            return self.status()

    def status(self) -> BundleStatus:
        with self._lock:
            return BundleStatus(
                active_bundle_id=self._active.manifest.bundle_id if self._active else None,
                previous_bundle_id=self._previous.manifest.bundle_id if self._previous else None,
                pinned_bundle_id=self._pinned,
            )

    def active_embedding_identity(self) -> EmbeddingIdentity | None:
        """Return the verified identity of the active immutable bundle."""

        with self._lock:
            return self._active.manifest.embedding if self._active is not None else None

    def verify(self, bundle_id: str) -> BundleManifest:
        """Verify one explicit retained bundle without changing activation state."""

        with self._lock:
            if not bundle_id or bundle_id not in self._retained_ids():
                raise BundleActivationError("bundle_verify_target_unknown")
            directory = self._bundles / bundle_id
            try:
                manifest = _load_manifest(directory / "manifest.json")
                verified = verify_retained_bundle_directory(
                    directory=directory,
                    expected_embedding=manifest.embedding,
                )
                if verified.manifest.bundle_id != bundle_id:
                    raise BundleActivationError("bundle_verify_target_incompatible")
                return verified.manifest
            except BundleActivationError:
                raise
            except Exception as exc:
                raise BundleActivationError("bundle_verify_target_incompatible") from exc
            finally:
                if "verified" in locals():
                    verified.close()

    def active_public_directory(self) -> Path | None:
        """Return the verified active bundle's immutable public directory."""

        with self._lock:
            if self._active is None:
                return None
            return self._active.directory / "public"

    def _activate_retained(self, bundle_id: str) -> None:
        directory = self._bundles / bundle_id
        try:
            verified = verify_retained_bundle_directory(
                directory=directory, expected_embedding=self._embedding
            )
            if verified.manifest.bundle_id != bundle_id:
                verified.close()
                raise BundleActivationError("bundle_pin_target_incompatible")
            promoted = _LiveBundle(directory, verified.manifest, verified.index)
            self._write_pointer(bundle_id)
        except Exception as exc:
            if "verified" in locals():
                verified.close()
            raise BundleActivationError("bundle_pin_target_incompatible") from exc
        previous = self._active
        self._active = promoted
        self._previous = previous
        if previous is not None:
            previous.retired = True
            self._close_if_retired(previous)

    def _write_pointer(self, bundle_id: str) -> None:
        temporary = self._pointer.with_name(f".{self._pointer.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps({"bundle_id": bundle_id}, separators=(",", ":")), encoding="utf-8"
            )
            os.replace(temporary, self._pointer)
        finally:
            temporary.unlink(missing_ok=True)

    def _restore_pointer(self, bundle_id: str | None) -> None:
        if bundle_id is None:
            self._pointer.unlink(missing_ok=True)
        else:
            self._write_pointer(bundle_id)

    def _fail_closed_restore_pointer(self, bundle_id: str | None) -> None:
        try:
            self._restore_pointer(bundle_id)
        except Exception:
            with suppress(OSError):
                self._pointer.unlink(missing_ok=True)

    def _restore_persisted_bundles(self, state: BundleRuntimeState) -> None:
        """Reopen validated active/previous handles after a process restart.

        The pointer is written before mutable runtime state, so it is preferred
        when both are present.  Every candidate is reopened through the normal
        manifest/read-only validation path; a stale or corrupt pointer leaves
        the manager safely unavailable instead of opening an arbitrary path.
        """

        pointer_id = self._pointer_bundle_id()
        active_candidates = tuple(
            bundle_id
            for bundle_id in (self._pinned, pointer_id, state.active_bundle_id)
            if bundle_id is not None
        )
        active: _LiveBundle | None = None
        for bundle_id in active_candidates:
            active = self._open_retained(bundle_id, allow_manifest_identity=True)
            if active is not None:
                break
        self._active = active
        if active is not None:
            self._embedding = active.manifest.embedding

        previous_candidates = tuple(
            bundle_id
            for bundle_id in (state.previous_bundle_id, state.active_bundle_id)
            if bundle_id is not None and (active is None or bundle_id != active.manifest.bundle_id)
        )
        for bundle_id in previous_candidates:
            previous = self._open_retained(bundle_id, allow_manifest_identity=True)
            if previous is not None:
                previous.retired = True
                self._previous = previous
                break

    def _pointer_bundle_id(self) -> str | None:
        try:
            payload = json.loads(self._pointer.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or set(payload) != {"bundle_id"}:
            return None
        bundle_id = payload.get("bundle_id")
        return bundle_id if isinstance(bundle_id, str) else None

    def _open_retained(
        self, bundle_id: str, *, allow_manifest_identity: bool = False
    ) -> _LiveBundle | None:
        directory = self._bundles / bundle_id
        if directory.parent != self._bundles or not directory.is_dir():
            return None
        try:
            expected_embedding = self._embedding
            if allow_manifest_identity:
                expected_embedding = _load_manifest(directory / "manifest.json").embedding
            verified = verify_retained_bundle_directory(
                directory=directory, expected_embedding=expected_embedding
            )
            if verified.manifest.bundle_id != bundle_id:
                verified.close()
                return None
            return _LiveBundle(directory, verified.manifest, verified.index)
        except Exception:
            if "verified" in locals():
                verified.close()
            return None

    def _persist_state(self) -> None:
        state = self._runtime.bundle_state()
        self._runtime.save_bundle_state(
            BundleRuntimeState(
                active_bundle_id=self._active.manifest.bundle_id if self._active else None,
                previous_bundle_id=self._previous.manifest.bundle_id if self._previous else None,
                pinned_bundle_id=self._pinned,
                manifest_etag=state.manifest_etag,
                last_checked_at=state.last_checked_at,
                safe_update_error=state.safe_update_error,
            )
        )

    def _retained_ids(self) -> set[str]:
        return {path.name for path in self._bundles.iterdir() if path.is_dir()}

    @staticmethod
    def _close_if_retired(live: _LiveBundle) -> None:
        if live.retired and live.leases == 0:
            live.index.close()

    def _cleanup_unreferenced(self) -> None:
        protected = {
            bundle_id
            for bundle_id in (
                self._active.manifest.bundle_id if self._active else None,
                self._previous.manifest.bundle_id if self._previous else None,
                self._pinned,
            )
            if bundle_id is not None
        }
        candidates = sorted(
            path for path in self._bundles.iterdir() if path.is_dir() and path.name not in protected
        )
        while len(candidates) + len(protected) > self._keep and candidates:
            shutil.rmtree(candidates.pop(0), ignore_errors=True)


def _load_manifest(path: Path) -> BundleManifest:
    from reponpc.bundles.manifest import parse_bundle_manifest

    return parse_bundle_manifest(path.read_bytes())


def _run_rollback(
    transition: ActivationTransition | Callable[[], None] | None,
) -> None:
    if transition is None:
        return
    with suppress(Exception):
        if isinstance(transition, ActivationTransition):
            transition.rollback()
        else:
            transition()
