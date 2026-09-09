"""Minimal RFC6455 WebSocket helpers (stdlib only)."""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from typing import Optional, Tuple

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def accept_key(sec_key: str) -> str:
    digest = hashlib.sha1((sec_key + GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def handshake_response(sec_key: str) -> bytes:
    ack = accept_key(sec_key)
    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {ack}\r\n"
        "\r\n"
    ).encode("ascii")


def encode_text(payload: str) -> bytes:
    data = payload.encode("utf-8")
    return _encode_frame(0x1, data)


def encode_close(code: int = 1000) -> bytes:
    return _encode_frame(0x8, struct.pack("!H", code))


def encode_pong(data: bytes = b"") -> bytes:
    return _encode_frame(0xA, data)


def _encode_frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < (1 << 16):
        header.append(126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", n))
    return bytes(header) + payload


def read_frame(recv) -> Tuple[int, bytes]:
    """Read one full frame. recv(n) must return exactly n bytes or raise."""
    hdr = _recvexact(recv, 2)
    opcode = hdr[0] & 0x0F
    masked = (hdr[1] & 0x80) != 0
    length = hdr[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recvexact(recv, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recvexact(recv, 8))[0]
    mask = _recvexact(recv, 4) if masked else b""
    data = _recvexact(recv, length) if length else b""
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data


def _recvexact(recv, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf.extend(chunk)
    return bytes(buf)
