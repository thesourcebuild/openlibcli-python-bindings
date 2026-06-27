"""
Pipe transport (Named & Anonymous pipes).

Provides read/write interface for Windows Named Pipes and POSIX FIFOs/pipes.
"""

from __future__ import annotations

import os
import sys
import platform
import select
import time
from typing import Any


from openlibcli.transports import BaseTransport, TRANSPORT_PIPE

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32

    # Win32 API functions for named pipes
    _PeekNamedPipe = kernel32.PeekNamedPipe
    _PeekNamedPipe.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    _PeekNamedPipe.restype = wintypes.BOOL

    _ReadFile = kernel32.ReadFile
    _ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    _ReadFile.restype = wintypes.BOOL

    _WriteFile = kernel32.WriteFile
    _WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    _WriteFile.restype = wintypes.BOOL

    _CloseHandle = kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL


class PipeTransport(BaseTransport):
    TRANSPORT_KIND = TRANSPORT_PIPE

    def __init__(self, r_handle: Any, w_handle: Any = None, timeout: float = 1.0) -> None:
        """Initialise PipeTransport.

        r_handle/w_handle can be:
        - Windows HANDLE (int)
        - POSIX file descriptor (int)
        - Python file-like object
        """
        super().__init__()
        self._r_obj = r_handle
        self._w_obj = w_handle if w_handle is not None else r_handle
        self.timeout = timeout

        self._r_fd: int | None = None
        self._w_fd: int | None = None
        self._r_win_handle: int | None = None
        self._w_win_handle: int | None = None

        if IS_WINDOWS:
            self._r_win_handle = self._get_win_handle(self._r_obj)
            self._w_win_handle = self._get_win_handle(self._w_obj)
        else:
            self._r_fd = self._get_posix_fd(self._r_obj)
            self._w_fd = self._get_posix_fd(self._w_obj)

    def _get_win_handle(self, obj: Any) -> int:
        if isinstance(obj, int):
            try:
                return msvcrt.get_osfhandle(obj)
            except OSError:
                return obj
        if hasattr(obj, "fileno"):
            try:
                fd = obj.fileno()
                return msvcrt.get_osfhandle(fd)
            except OSError:
                pass
        return 0

    def _get_posix_fd(self, obj: Any) -> int:
        if isinstance(obj, int):
            return obj
        if hasattr(obj, "fileno"):
            return obj.fileno()
        raise ValueError("Invalid file descriptor or object")

    def _available(self) -> int:
        if IS_WINDOWS:
            if not self._r_win_handle:
                return -1
            avail = wintypes.DWORD(0)
            start_time = time.time()
            while True:
                success = _PeekNamedPipe(
                    self._r_win_handle, None, 0, None, ctypes.byref(avail), None
                )
                if not success:
                    return -1
                if avail.value > 0:
                    return 1
                if self.timeout <= 0 or (time.time() - start_time) >= self.timeout:
                    break
                time.sleep(0.01)
            return 0
        else:
            if self._r_fd is None:
                return -1
            try:
                r, _, _ = select.select([self._r_fd], [], [], self.timeout)
                return 1 if r else 0
            except OSError:
                return -1


    def _read_into(self, buf: bytearray) -> int:
        if IS_WINDOWS:
            if not self._r_win_handle:
                return -1
            avail = wintypes.DWORD(0)
            # Check if there is data in the pipe first to prevent blocking
            success = _PeekNamedPipe(
                self._r_win_handle, None, 0, None, ctypes.byref(avail), None
            )
            if not success:
                # Might be broken pipe or not a named pipe (e.g. anonymous file/stream)
                # Try reading anyway
                pass
            elif avail.value == 0:
                return 0

            read_bytes = wintypes.DWORD(0)
            c_buf = (ctypes.c_char * len(buf)).from_buffer(buf)
            ok = _ReadFile(
                self._r_win_handle,
                c_buf,
                len(buf),
                ctypes.byref(read_bytes),
                None,
            )
            if not ok:
                err = kernel32.GetLastError()
                if err in (109, 232):  # ERROR_BROKEN_PIPE, ERROR_NO_DATA
                    return -1
                return -1
            return read_bytes.value
        else:
            if self._r_fd is None:
                return -1
            try:
                r, _, _ = select.select([self._r_fd], [], [], 0)
                if not r:
                    return 0
                data = os.read(self._r_fd, len(buf))
                if not data:
                    return -1  # EOF
                buf[:len(data)] = data
                return len(data)
            except (OSError, ValueError):
                return -1

    def _write(self, data: bytes) -> int:
        if IS_WINDOWS:
            if not self._w_win_handle:
                return -1
            written = wintypes.DWORD(0)
            ok = _WriteFile(
                self._w_win_handle,
                data,
                len(data),
                ctypes.byref(written),
                None,
            )
            if not ok:
                return -1
            return written.value
        else:
            if self._w_fd is None:
                return -1
            try:
                return os.write(self._w_fd, data)
            except OSError:
                return -1

    def _flush(self) -> int:
        return 0

    def close(self) -> None:
        if IS_WINDOWS:
            # We don't close Windows handles if we didn't open them directly,
            # but we can try to close if requested.
            pass
        else:
            try:
                if hasattr(self._r_obj, "close"):
                    self._r_obj.close()
                if hasattr(self._w_obj, "close") and self._w_obj is not self._r_obj:
                    self._w_obj.close()
            except OSError:
                pass
