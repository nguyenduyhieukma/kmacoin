from kmacoin.globaldef.signature import PUBLIC_KEY_SIZE

from typing import BinaryIO


class Coin(object):
    """
    This class represents a coin in KMA-Coin system.

    Attributes:
        owner: the coin's owner.
        value: the coin's value.

    """

    # All field sizes:
    OWNER_FSZ = PUBLIC_KEY_SIZE
    VALUE_FSZ = 4
    SIZE = OWNER_FSZ + VALUE_FSZ

    # Deduced limits:
    MAX_VALUE = 2 ** (8*VALUE_FSZ)

    def __init__(self, owner: bytes, value: int):
        assert len(owner) == Coin.OWNER_FSZ
        assert 0 < value <= Coin.MAX_VALUE
        self.owner = owner
        self.value = value

    def to_bytes(self) -> bytes:
        """Serialize this coin."""
        value = self.value if self.value < Coin.MAX_VALUE else 0
        return self.owner + value.to_bytes(Coin.VALUE_FSZ, "big")

    def write_to(self, w: BinaryIO) -> None:
        """Write this coin to a bytestream."""
        w.write(self.to_bytes())

    @staticmethod
    def read_from(r: BinaryIO) -> 'Coin':
        """Read a coin from a bytestream."""
        owner = r.read(Coin.OWNER_FSZ)
        value = int.from_bytes(r.read(Coin.VALUE_FSZ), "big")
        if value == 0:
            value = Coin.MAX_VALUE
        return Coin(owner, value)
