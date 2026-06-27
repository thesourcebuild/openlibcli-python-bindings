"""
UNIX Domain Socket transport.

Provides read/write to the CLI engine via a UNIX Domain Socket.
"""

from __future__ import annotations

import errno
import select
import socket

from openlibcli.transports import BaseTransport, TRANSPORT_UNIX_SOCKET


class UnixSocketTransport(BaseTransport):
    TRANSPORT_KIND = TRANSPORT_UNIX_SOCKET

    def __init__(self, sock: socket.socket, timeout: float = 1.0) -> None:
        super().__init__()
        self._sock = sock
        self._sock.setblocking(False)
        self.timeout = timeout

    def _available(self) -> int:
        try:
            r, _, _ = select.select([self._sock], [], [], self.timeout)
            return 1 if r else 0
        except OSError:
            return -1

    def _read_into(self, buf: bytearray) -> int:
        try:
            r, _, _ = select.select([self._sock], [], [], 0)
            if not r:
                return 0
            data = self._sock.recv(len(buf))
            if not data:
                return -1  # remote closed
            buf[:len(data)] = data
            return len(data)
        except (socket.timeout, BlockingIOError):
            return 0
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return 0
            return -1

    def _write(self, data: bytes) -> int:
        try:
            return self._sock.send(data)
        except OSError:
            return -1

    def _flush(self) -> int:
        return 0

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
