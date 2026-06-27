"""
Transport base class and built-in transport implementations.

Every transport subclasses ``BaseTransport`` and implements
``_read_into(buffer: bytearray) -> int``,
``_write(buffer: bytes) -> int``, and optionally ``_flush()``.
"""

from __future__ import annotations

import ctypes
import sys
from typing import ClassVar

from .. import _binding as _b

_CliTransportPointer = ctypes.POINTER(_b.CliTransport)

# Transport kind constants (mirror cli_transport_kind_t enum)
TRANSPORT_UNKNOWN = 0
TRANSPORT_TELNET = 1
TRANSPORT_TCP = 2
TRANSPORT_SERIAL = 3
TRANSPORT_PIPE = 4
TRANSPORT_UNIX_SOCKET = 5


class BaseTransport:
    """Base class for Python transport implementations.

    Subclasses must implement ``_read_into`` and ``_write``.
    """

    TRANSPORT_KIND: ClassVar[int] = TRANSPORT_SERIAL  # override in subclass

    def __init__(self) -> None:
        # Keep the ctypes callback objects alive (prevents GC)
        self._available_cb: _b.TRANSPORT_AVAILABLE_FN | None = None
        self._read_cb: _b.TRANSPORT_READ_FN | None = None
        self._write_cb: _b.TRANSPORT_WRITE_FN | None = None
        self._flush_cb: _b.TRANSPORT_FLUSH_FN | None = None
        self._c_transport: _b.CliTransport | None = None
        self.exception: BaseException | None = None

    def _available(self) -> int:
        """Return 1 if data is available, 0 if not, negative on error."""
        return 1

    def _read_into(self, buf: bytearray) -> int:
        """Read up to len(buf) bytes into buf. Return bytes read, 0 for no data, negative on error."""
        raise NotImplementedError

    def _write(self, data: bytes) -> int:
        """Write all of data. Return bytes written, negative on error."""
        raise NotImplementedError

    def _flush(self) -> int:
        """Optional flush. Return 0 on success, negative on error."""
        return 0

    def _make_ctypes_callbacks(self) -> None:
        """Create ctypes callback functions that bridge C -> Python."""
        ctx_ptr = id(self)
        _b._register_transport(ctx_ptr, self)

        @_b.TRANSPORT_AVAILABLE_FN
        def _available(c_ctx):
            try:
                return self._available()
            except BaseException as e:
                self.exception = e
                return -1

        @_b.TRANSPORT_READ_FN
        def _read(c_ctx):
            try:
                buf = bytearray(1)
                n = self._read_into(buf)
                if n > 0:
                    return buf[0]
                if n == 0:
                    return 0
                return -1
            except BaseException as e:
                self.exception = e
                return -1

        @_b.TRANSPORT_WRITE_FN
        def _write(c_ctx, c_buf, c_len):
            try:
                length = c_len.value if hasattr(c_len, 'value') else c_len
                data = ctypes.string_at(c_buf, length)
                return self._write(data)
            except BaseException as e:
                self.exception = e
                return -1

        @_b.TRANSPORT_FLUSH_FN
        def _flush(c_ctx):
            try:
                return self._flush()
            except BaseException as e:
                self.exception = e
                return -1

        self._available_cb = _available
        self._read_cb = _read
        self._write_cb = _write
        self._flush_cb = _flush

    def _build_c_transport(self) -> _CliTransportPointer:
        """Build and return a pointer to a C ``cli_transport_t`` struct."""
        if self._c_transport is None:
            self._make_ctypes_callbacks()
            self._c_transport = _b.make_transport(
                self.TRANSPORT_KIND,
                self._available_cb,
                self._read_cb,
                self._write_cb,
                self._flush_cb,
                id(self),
            )
        return ctypes.pointer(self._c_transport)
