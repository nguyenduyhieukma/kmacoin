"""
This module implements the hash algorithm used by KMA-Coin.

By default, SHA256 is used.

For simplicity, only one function needs to be defined:
    kma_hash(inp: bytes) -> bytes

"""
import hashlib


def kma_hash(inp: bytes) -> bytes:
    """The global hash function used by KMA-Coin."""
    return hashlib.sha256(inp).digest()


# The constants below are automatically calculated:
HASH_OF_NULL = kma_hash(b"\x00")
HASH_SIZE = len(HASH_OF_NULL)
