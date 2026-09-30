"""Time-ordered UUIDv7 identifiers (RFC 9562) for primary keys.

Time ordering keeps B-tree indexes compact and makes IDs sortable by creation.
"""

from __future__ import annotations

import os
import time
import uuid

_RAND_A_MASK = (1 << 12) - 1
_RAND_B_MASK = (1 << 62) - 1


def uuid7() -> uuid.UUID:
    unix_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (unix_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= ((rand >> 62) & _RAND_A_MASK) << 64
    value |= 0b10 << 62  # RFC 4122 variant
    value |= rand & _RAND_B_MASK
    return uuid.UUID(int=value)
