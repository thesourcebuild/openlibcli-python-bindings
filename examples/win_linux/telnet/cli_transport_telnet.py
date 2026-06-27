"""
Telnet server transport.

Wraps an accepted TCP socket with telnet protocol negotiation
(IAC, WILL/WONT/DO/DONT, SB, escape translation).

Usage::

    import socket
    from openlibcli.transports.telnet import TelnetTransport

    server = socket.socket()
    server.bind(("0.0.0.0", 2323))
    server.listen(5)

    while True:
        client, addr = server.accept()
        transport = TelnetTransport(client)
        session = cli.Session("router", transport, cmd_pool_size=256)
        # ... add commands, start session loop
"""

from __future__ import annotations

import errno
import select
import socket
import platform
from typing import ClassVar

from openlibcli.transports import BaseTransport, TRANSPORT_TELNET

IS_WINDOWS = platform.system() == "Windows"

# Telnet constants
IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240
NOP = 241

TELNET_OPT_ECHO = 1
TELNET_OPT_SGA = 3
TELNET_OPT_NAWS = 31
TELNET_OPT_LINEMODE = 34

# Telnet state machine states
TELNET_STATE_NORMAL = 0
TELNET_STATE_IAC = 1
TELNET_STATE_VERB = 2
TELNET_STATE_SB = 3
TELNET_STATE_SB_IAC = 4

# Escape sequence map: byte3 → control char
ESC_MAP: dict[int, int] = {
    0x48: 0x1B,  # up arrow → ESC (history up)
    0x50: 0x0A,  # down arrow → LF (history down)
    0x4D: 0x0C,  # right arrow → FF (forward char)
    0x4B: 0x08,  # left arrow → BS (backward char)
    0x47: 0x01,  # Home → Ctrl-A
    0x4F: 0x05,  # End → Ctrl-E
    0x53: 0x04,  # Delete → Ctrl-D
}


class TelnetTransport(BaseTransport):
    TRANSPORT_KIND = TRANSPORT_TELNET

    def __init__(self, sock: socket.socket, timeout: float = 1.0) -> None:
        super().__init__()
        self._sock = sock
        self._sock.setblocking(False)
        self.timeout = timeout

        # Telnet state
        self._state = TELNET_STATE_NORMAL
        self._verb = 0
        self._negotiated = False
        self._local_echo = False
        self._local_sga = False

        # RX buffer (after telnet processing).
        # _rx_pos: next byte to consume.
        # _rx_len: number of valid bytes from index 0.
        self._rx_buf = bytearray(256)
        self._rx_len = 0
        self._rx_pos = 0

        # Send initial negotiation
        self._negotiate()

    def _send(self, data: bytes) -> None:
        """Send raw bytes (blocking, best-effort)."""
        try:
            self._sock.setblocking(True)
            self._sock.sendall(data)
        except OSError:
            pass
        finally:
            self._sock.setblocking(False)

    def _negotiate(self) -> None:
        """Send WILL ECHO, WILL SGA, DONT LINEMODE, DO NAWS."""
        negotiation = bytes([
            IAC, WILL, TELNET_OPT_ECHO,
            IAC, WILL, TELNET_OPT_SGA,
            IAC, DONT, TELNET_OPT_LINEMODE,
            IAC, DO, TELNET_OPT_NAWS,
        ])
        self._send(negotiation)
        self._negotiated = True
        self._local_echo = True
        self._local_sga = True

    def _respond(self, verb: int, opt: int) -> None:
        """Respond to a telnet negotiation request."""
        send_resp = True
        response = bytearray([IAC, 0, opt])

        if verb == DO:
            if opt == TELNET_OPT_ECHO:
                send_resp = not self._local_echo
                self._local_echo = True
                response[1] = WILL
            elif opt == TELNET_OPT_SGA:
                send_resp = not self._local_sga
                self._local_sga = True
                response[1] = WILL
            else:
                response[1] = WONT
        elif verb == DONT:
            if opt == TELNET_OPT_ECHO and self._local_echo:
                self._local_echo = False
                response[1] = WONT
            elif opt == TELNET_OPT_SGA and self._local_sga:
                self._local_sga = False
                response[1] = WONT
            else:
                send_resp = False
        elif verb == WILL:
            if opt == TELNET_OPT_NAWS:
                send_resp = False
            elif opt == TELNET_OPT_LINEMODE:
                send_resp = False
            else:
                response[1] = DONT
        elif verb == WONT:
            send_resp = False

        if send_resp:
            self._send(bytes(response))

    def _fill_buffer(self, timeout: float = 0.0) -> int:
        """Read raw bytes from the socket, process telnet states, translate escapes.

        Compacts already-consumed bytes first so that _rx_len always
        represents the number of valid bytes starting at index 0.

        Returns 0 on success, negative on EOF/error.
        """
        # Compact: shift unconsumed bytes to the front of the buffer
        if self._rx_pos > 0:
            remaining = self._rx_len - self._rx_pos
            if remaining > 0:
                self._rx_buf[:remaining] = self._rx_buf[self._rx_pos:self._rx_len]
            self._rx_len = remaining
            self._rx_pos = 0

        try:
            r, _, _ = select.select([self._sock], [], [], timeout)
            if not r:
                return 0
            raw = self._sock.recv(1024)
        except (socket.timeout, BlockingIOError):
            return 0
        except OSError as e:
            if getattr(e, 'winerror', None) == 10035:
                return 0
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return 0
            return -1

        if not raw:
            return -1  # remote closed

        # Process each byte through the telnet state machine
        i = 0
        while i < len(raw) and self._rx_len < len(self._rx_buf):
            byte = raw[i]
            i += 1

            if self._state == TELNET_STATE_NORMAL:
                if byte == IAC:
                    self._state = TELNET_STATE_IAC
                elif byte != 0:
                    self._rx_buf[self._rx_len] = byte
                    self._rx_len += 1

            elif self._state == TELNET_STATE_IAC:
                if byte == IAC:
                    # Escaped 0xFF → data
                    self._rx_buf[self._rx_len] = 0xFF
                    self._rx_len += 1
                    self._state = TELNET_STATE_NORMAL
                elif byte in (DO, DONT, WILL, WONT):
                    self._verb = byte
                    self._state = TELNET_STATE_VERB
                elif byte == SB:
                    self._state = TELNET_STATE_SB
                elif byte == NOP:
                    self._state = TELNET_STATE_NORMAL
                else:
                    # Unknown IAC command — ignore
                    self._state = TELNET_STATE_NORMAL

            elif self._state == TELNET_STATE_VERB:
                self._respond(self._verb, byte)
                self._state = TELNET_STATE_NORMAL

            elif self._state == TELNET_STATE_SB:
                if byte == IAC:
                    self._state = TELNET_STATE_SB_IAC

            elif self._state == TELNET_STATE_SB_IAC:
                if byte == SE:
                    self._state = TELNET_STATE_NORMAL
                else:
                    self._state = TELNET_STATE_SB

        # Handle escape sequences (arrow keys etc.)
        self._translate_escape_sequences()
        return 0

    def _available(self) -> int:
        if self._rx_pos < self._rx_len:
            return 1
        rc = self._fill_buffer(timeout=self.timeout)
        if rc < 0:
            return -1
        return 1 if self._rx_pos < self._rx_len else 0

    def _read_into(self, buf: bytearray) -> int:
        # Drain any buffered processed data
        if self._rx_pos < self._rx_len:
            pending = self._rx_len - self._rx_pos
            if pending > len(buf):
                pending = len(buf)
            buf[:pending] = self._rx_buf[self._rx_pos:self._rx_pos + pending]
            self._rx_pos += pending
            return pending

        # Refill buffer if needed
        rc = self._fill_buffer()
        if rc < 0:
            return -1

        if self._rx_pos < self._rx_len:
            pending = self._rx_len - self._rx_pos
            if pending > len(buf):
                pending = len(buf)
            buf[:pending] = self._rx_buf[self._rx_pos:self._rx_pos + pending]
            self._rx_pos += pending
            return pending

        return 0

    def _translate_escape_sequences(self) -> int:
        """Translate \\x1B[A style CSI sequences to single control bytes."""
        if self._rx_len < 3 or self._rx_buf[0] != 0x1B or self._rx_buf[1] != ord('['):
            return 0
        n = 2
        while n < self._rx_len and self._rx_buf[n] in (0x3B, 0x7E) or (
            0x30 <= self._rx_buf[n] <= 0x39
        ):
            n += 1
        if n < self._rx_len:
            byte3 = self._rx_buf[n]
            if byte3 in ESC_MAP:
                self._rx_buf[0] = ESC_MAP[byte3]
                rest = n + 1 - 1
                if rest > 0 and rest < len(self._rx_buf):
                    self._rx_buf[1:self._rx_len - rest] = self._rx_buf[rest:self._rx_len]
                self._rx_len -= rest
                return 1
        return 0

    def _write(self, data: bytes) -> int:
        # Escape any 0xFF bytes with IAC IAC
        try:
            escaped = data.replace(bytes([0xFF]), bytes([IAC, IAC]))
            self._sock.setblocking(True)
            self._sock.sendall(escaped)
            return len(data)
        except OSError:
            return -1
        finally:
            self._sock.setblocking(False)

    def _flush(self) -> int:
        return 0

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
