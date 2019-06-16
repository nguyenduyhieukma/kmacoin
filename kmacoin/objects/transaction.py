from kmacoin.globaldef.hash import kma_hash, HASH_SIZE
from kmacoin.globaldef.signature import SIGNATURE_SIZE
from kmacoin.objects.coin import Coin

from typing import List, Tuple, BinaryIO


class Transaction(object):
    """
    This class represents a transaction in KMA-Coin system.

    Attributes:
        input_ids: IDs of coins to be destroyed by this transaction.
        outputs: a list of coins to be created.
        sigs: a list of signatures signed by input coins' owners.
        id: the transaction's ID.

    """

    # All field sizes:
    INPUT_COUNT_FSZ = 1
    OUTPUT_COUNT_FSZ = 1
    SIG_COUNT_FSZ = 1
    TX_ID_FSZ = HASH_SIZE
    SEQ_FSZ = 1
    COIN_FSZ = Coin.SIZE
    SIG_FSZ = SIGNATURE_SIZE

    # Deduced limits:
    MAX_INPUTS = 2 ** (8*INPUT_COUNT_FSZ) - 1
    MAX_OUTPUTS = 2 ** (8*OUTPUT_COUNT_FSZ) - 1
    MAX_SIGS = 2 ** (8*SIG_COUNT_FSZ) - 1
    MAX_SEQ = MAX_OUTPUTS - 1
    assert 2 ** (8*SEQ_FSZ) >= MAX_SEQ + 1

    def __init__(self, input_ids: List[Tuple[bytes, int]],
                 outputs: List[Coin]):
        assert len(input_ids) <= Transaction.MAX_INPUTS
        for tx_id, seq in input_ids:
            assert len(tx_id) == Transaction.TX_ID_FSZ
            assert 0 <= seq <= Transaction.MAX_SEQ
        assert len(outputs) <= Transaction.MAX_OUTPUTS
        self.input_ids = input_ids
        self.outputs = outputs
        self.sigs = []
        self.id = None

    def get_data_to_be_signed(self):
        """Get the data to be signed by owners of input coins."""
        return b"".join(
            tx_id + seq.to_bytes(Transaction.SEQ_FSZ, "big")
            for tx_id, seq in self.input_ids
        ) + b"".join(coin.to_bytes() for coin in self.outputs)

    def get_signed_data(self):
        """An alias of `get_data_to_be_signed`."""
        return self.get_data_to_be_signed()

    def add_signature(self, sig: bytes) -> None:
        """Add a signature to this transaction."""
        assert len(sig) == Transaction.SIG_FSZ
        assert len(self.sigs) < len(self.input_ids)
        self.sigs.append(sig)
        self.id = None  # reset the ID

    def to_bytes(self) -> bytes:
        """Serialize this transaction."""
        return (
            len(self.input_ids).to_bytes(Transaction.INPUT_COUNT_FSZ, "big") +
            len(self.outputs).to_bytes(Transaction.OUTPUT_COUNT_FSZ, "big") +
            len(self.sigs).to_bytes(Transaction.SIG_COUNT_FSZ, "big") +
            self.get_signed_data() +
            b"".join(self.sigs)
        )

    def get_id(self) -> bytes:
        """Get the ID of this transaction."""
        if not self.id:
            self.id = kma_hash(self.to_bytes())
        return self.id

    def write_to(self, w: BinaryIO) -> None:
        """Write this transaction to a bytestream."""
        w.write(self.to_bytes())

    @staticmethod
    def read_from(r: BinaryIO) -> 'Transaction':
        """Read a transaction from a bytestream."""

        # get counts
        ic = int.from_bytes(r.read(Transaction.INPUT_COUNT_FSZ), "big")
        oc = int.from_bytes(r.read(Transaction.OUTPUT_COUNT_FSZ), "big")
        sc = int.from_bytes(r.read(Transaction.SIG_COUNT_FSZ), "big")

        # parse input coin IDs
        input_ids = []
        for i in range(ic):
            tx_id = r.read(Transaction.TX_ID_FSZ)
            seq = int.from_bytes(r.read(Transaction.SEQ_FSZ), "big")
            input_ids.append((tx_id, seq))

        # parse outputs
        outputs = []
        for i in range(oc):
            outputs.append(Coin.read_from(r))

        # parse signatures
        tx = Transaction(input_ids, outputs)
        for i in range(sc):
            tx.add_signature(r.read(Transaction.SIG_FSZ))

        return tx
