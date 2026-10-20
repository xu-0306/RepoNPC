"""Owner-only file and directory permissions for private runtime material."""

from __future__ import annotations

import stat
import struct
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

_SYSTEM_SID: Final = "S-1-5-18"
_ADMINISTRATORS_SID: Final = "S-1-5-32-544"
_CREATOR_OWNER_SID: Final = "S-1-3-0"
# OWNER RIGHTS grants only the object owner, which the check limits to the user or
# Administrators. Python 3.13+ uses it for mkdir(mode=0o700) on Windows.
_OWNER_RIGHTS_SID: Final = "S-1-3-4"

_ACCESS_ALLOWED_ACE_TYPE: Final = 0
# Access-denied and audit ACE types grant nothing; any other type may grant access.
_NON_GRANTING_ACE_TYPES: Final = frozenset({1, 2, 3, 6, 7, 8, 10, 12, 13, 14})
_INHERIT_ONLY_ACE: Final = 0x08


def _evaluate_owner_only_acl(
    owner_sid: str | None,
    entries: Sequence[tuple[int, int, str]],
    user_sid: str,
    *,
    dacl_present: bool = True,
) -> bool:
    """Evaluate a parsed DACL of ``(ACE type, ACE flags, SID)`` entries.

    Only the current user, SYSTEM, Administrators and the owner (which must be
    the user or Administrators) may be granted access,
    explicitly or by inheritance. An allow-type ACE that cannot be parsed fails.
    """

    if not dacl_present or owner_sid not in {user_sid, _ADMINISTRATORS_SID}:
        return False
    allowed = {user_sid, _SYSTEM_SID, _ADMINISTRATORS_SID, _OWNER_RIGHTS_SID}
    for ace_type, flags, sid in entries:
        if ace_type in _NON_GRANTING_ACE_TYPES:
            continue
        if ace_type != _ACCESS_ALLOWED_ACE_TYPE:
            return False
        if sid == _CREATOR_OWNER_SID and flags & _INHERIT_ONLY_ACE:
            continue
        if sid not in allowed:
            return False
    return True


def restrict_owner_only(path: Path) -> None:
    """Restrict one existing file or directory to its owner and system accounts."""

    if sys.platform == "win32":
        _restrict_windows(path)
        return
    path.chmod(stat.S_IRWXU if path.is_dir() else stat.S_IRUSR | stat.S_IWUSR)


def is_owner_only(path: Path, *, posix_forbidden_mode: int) -> bool:
    """Return whether ``path`` satisfies the owner-only policy.

    POSIX callers pass the mode bits they forbid. Windows checks the DACL and
    fails closed when it cannot be read.
    """

    if sys.platform == "win32":
        try:
            owner, entries, dacl_present = _read_windows_acl(path)
            return _evaluate_owner_only_acl(
                owner, entries, _current_user_sid(), dacl_present=dacl_present
            )
        except OSError:
            return False
    return not path.stat().st_mode & posix_forbidden_mode


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _SE_FILE_OBJECT = 1
    _OWNER_SECURITY_INFORMATION = 0x00000001
    _DACL_SECURITY_INFORMATION = 0x00000004
    _PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
    _ACL_REVISION = 2
    _TOKEN_QUERY = 0x0008
    _TOKEN_USER = 1
    _OBJECT_INHERIT_ACE = 0x01
    _CONTAINER_INHERIT_ACE = 0x02
    _GENERIC_ALL = 0x10000000

    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _pointer = ctypes.c_void_p
    _out_pointer = ctypes.POINTER(ctypes.c_void_p)

    _kernel32.GetCurrentProcess.argtypes = []
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [_pointer]
    _kernel32.LocalFree.restype = _pointer
    _advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    _advapi32.OpenProcessToken.restype = wintypes.BOOL
    _advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        _pointer,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _advapi32.GetTokenInformation.restype = wintypes.BOOL
    _advapi32.ConvertSidToStringSidW.argtypes = [_pointer, ctypes.POINTER(wintypes.LPWSTR)]
    _advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    _advapi32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, _out_pointer]
    _advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    # owner, group, DACL, SACL, security descriptor
    _advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        _out_pointer,
        _out_pointer,
        _out_pointer,
        _out_pointer,
        _out_pointer,
    ]
    _advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    # owner, group, DACL, SACL
    _advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        _pointer,
        _pointer,
        _pointer,
        _pointer,
    ]
    _advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    _advapi32.GetAce.argtypes = [_pointer, wintypes.DWORD, _out_pointer]
    _advapi32.GetAce.restype = wintypes.BOOL
    _advapi32.IsValidSid.argtypes = [_pointer]
    _advapi32.IsValidSid.restype = wintypes.BOOL
    _advapi32.GetLengthSid.argtypes = [_pointer]
    _advapi32.GetLengthSid.restype = wintypes.DWORD
    _advapi32.InitializeAcl.argtypes = [_pointer, wintypes.DWORD, wintypes.DWORD]
    _advapi32.InitializeAcl.restype = wintypes.BOOL
    _advapi32.AddAccessAllowedAceEx.argtypes = [
        _pointer,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        _pointer,
    ]
    _advapi32.AddAccessAllowedAceEx.restype = wintypes.BOOL

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

    def _check(succeeded: object) -> None:
        if not succeeded:
            raise ctypes.WinError(ctypes.get_last_error())

    def _check_status(status: int) -> None:
        if status:
            raise ctypes.WinError(status)

    def _sid_string(sid: int | None) -> str:
        if not sid or not _advapi32.IsValidSid(sid):
            raise OSError("invalid SID")
        text = wintypes.LPWSTR()
        _check(_advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)))
        try:
            return str(text.value)
        finally:
            _kernel32.LocalFree(ctypes.cast(text, ctypes.c_void_p))

    def _current_user_sid() -> str:
        token = wintypes.HANDLE()
        _check(
            _advapi32.OpenProcessToken(
                _kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
            )
        )
        try:
            size = wintypes.DWORD()
            _advapi32.GetTokenInformation(token, _TOKEN_USER, None, 0, ctypes.byref(size))
            buffer = ctypes.create_string_buffer(size.value)
            _check(
                _advapi32.GetTokenInformation(token, _TOKEN_USER, buffer, size, ctypes.byref(size))
            )
            return _sid_string(_SidAndAttributes.from_buffer(buffer).Sid)
        finally:
            _kernel32.CloseHandle(token)

    def _read_windows_acl(path: Path) -> tuple[str | None, list[tuple[int, int, str]], bool]:
        owner = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        _check_status(
            _advapi32.GetNamedSecurityInfoW(
                str(path),
                _SE_FILE_OBJECT,
                _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
                ctypes.byref(owner),
                None,
                ctypes.byref(dacl),
                None,
                ctypes.byref(descriptor),
            )
        )
        try:
            owner_sid = _sid_string(owner.value)
            if not dacl.value:
                return owner_sid, [], False
            _, _, _, ace_count, _ = struct.unpack("<BBHHH", ctypes.string_at(dacl.value, 8))
            entries: list[tuple[int, int, str]] = []
            for index in range(ace_count):
                ace = ctypes.c_void_p()
                _check(_advapi32.GetAce(dacl, index, ctypes.byref(ace)))
                if not ace.value:
                    raise OSError("missing ACE")
                ace_type, flags, _ = struct.unpack("<BBH", ctypes.string_at(ace.value, 4))
                # ACCESS_ALLOWED_ACE: 4-byte header, 4-byte mask, then the SID.
                sid = _sid_string(ace.value + 8) if ace_type == _ACCESS_ALLOWED_ACE_TYPE else ""
                entries.append((ace_type, flags, sid))
            return owner_sid, entries, True
        finally:
            _kernel32.LocalFree(descriptor)

    def _restrict_windows(path: Path) -> None:
        sids: list[ctypes.c_void_p] = []
        try:
            for text in (_current_user_sid(), _SYSTEM_SID, _ADMINISTRATORS_SID):
                sid = ctypes.c_void_p()
                _check(_advapi32.ConvertStringSidToSidW(text, ctypes.byref(sid)))
                sids.append(sid)
            # ACL header plus one ACCESS_ALLOWED_ACE (header and mask) per SID.
            size = 8 + sum(8 + _advapi32.GetLengthSid(sid) for sid in sids)
            acl = ctypes.create_string_buffer(size)
            _check(_advapi32.InitializeAcl(ctypes.addressof(acl), size, _ACL_REVISION))
            flags = _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE if path.is_dir() else 0
            for sid in sids:
                _check(
                    _advapi32.AddAccessAllowedAceEx(
                        ctypes.addressof(acl), _ACL_REVISION, flags, _GENERIC_ALL, sid
                    )
                )
            _check_status(
                _advapi32.SetNamedSecurityInfoW(
                    str(path),
                    _SE_FILE_OBJECT,
                    _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION,
                    None,
                    None,
                    ctypes.addressof(acl),
                    None,
                )
            )
        finally:
            for sid in sids:
                _kernel32.LocalFree(sid)

else:

    def _current_user_sid() -> str:
        raise OSError("Windows security APIs are unavailable")

    def _read_windows_acl(path: Path) -> tuple[str | None, list[tuple[int, int, str]], bool]:
        raise OSError("Windows security APIs are unavailable")

    def _restrict_windows(path: Path) -> None:
        raise OSError("Windows security APIs are unavailable")
