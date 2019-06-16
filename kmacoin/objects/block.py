from kmacoin.globaldef.hash import kma_hash, HASH_SIZE
from kmacoin.objects.transaction import Transaction

from typing import List, BinaryIO, Optional

import time


class Block(object):
    """
    This class represents a block in KMA-Coin system.

    Attributes:
        timestamp: the block's announcement time.
        nonce: the solution to `hash(block) < threshold`
        prev_id: the previous block's ID.
        txs: the block's transactions.
        id: the block's ID.

    """
    nonce: Optional[bytes]
    txs: List[Transaction]
    id: Optional[bytes]

    # All field sizes:
    TIMESTAMP_FSZ = 4
    NONCE_FSZ = 4
    PREV_ID_FSZ = HASH_SIZE
    TX_COUNT_FSZ = 2
    ID_FSZ = PREV_ID_FSZ

    # Deduced limits:
    MAX_TXS = 2 ** (8*TX_COUNT_FSZ) - 1

    def __init__(self, prev_id: bytes):
        assert len(prev_id) == Block.PREV_ID_FSZ
        self.timestamp = int(time.time())
        self.nonce = None
        self.prev_id = prev_id
        self.txs = []
        self.id = None

    def update_timestamp(self) -> None:
        """Update this block's timestamp."""
        self.timestamp = int(time.time())
        self.id = None

    def add_transaction(self, tx: Transaction) -> None:
        """Add a transaction to this block."""
        self.txs.append(tx)
        self.id = None

    def replace_transaction(self, index: int, tx: Transaction) -> None:
        """
        Replace a transaction in this block.

        Args:
            index: index of old transaction.
            tx: a new transaction to be replaced with.

        """
        self.txs[index] = tx
        self.id = None

    def clear_transactions(self) -> None:
        """Clear all transactions in this block."""
        self.txs = []
        self.id = None

    def set_nonce(self, nonce: bytes) -> None:
        """Set this block's nonce."""
        assert len(nonce) == Block.NONCE_FSZ
        self.nonce = nonce
        self.id = None

    def to_bytes(self) -> bytes:
        """Serialize this block."""
        assert self.nonce
        assert len(self.txs) < Block.MAX_TXS
        return (
            self.timestamp.to_bytes(Block.TIMESTAMP_FSZ, "big") +
            self.nonce +
            self.prev_id +
            len(self.txs).to_bytes(Block.TX_COUNT_FSZ, "big") +
            b"".join(tx.to_bytes() for tx in self.txs)
        )

    def get_id(self):
        """Get this block's ID"""
        if not self.id:
            self.id = kma_hash(self.to_bytes())
        return self.id

    def write_to(self, w: BinaryIO) -> None:
        """Write this block to a bytestream."""
        w.write(self.to_bytes())

    @staticmethod
    def read_from(r: BinaryIO) -> 'Block':
        """Read a block from a bytestream."""

        # get block's metadata
        timestamp = int.from_bytes(r.read(Block.TIMESTAMP_FSZ), "big")
        nonce = r.read(Block.NONCE_FSZ)
        prev_id = r.read(Block.PREV_ID_FSZ)
        tx_count = int.from_bytes(r.read(Block.TX_COUNT_FSZ), "big")

        # get all transactions
        txs = [Transaction.read_from(r) for _ in range(tx_count)]

        # construct the result block
        block = Block(prev_id)
        block.timestamp = timestamp
        block.nonce = nonce
        block.txs = txs
        return block
