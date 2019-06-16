from kmacoin.objects.transaction import Transaction
from kmacoin.objects.block import Block
from kmacoin.network.vlp import VLPSocket
from kmacoin.network.protocol import Protocol

from typing import Tuple, Optional


class KMASocket(VLPSocket):
    """A subclass of VLPSocket, adding KMA-Coin objects send/recv functions."""
    @staticmethod
    def from_vlpsocket(vlpsocket: VLPSocket) -> 'KMASocket':
        """Cast a VLP socket to a KMA socket."""
        return KMASocket(vlpsocket.virt_loc, vlpsocket.s,
                         vlpsocket.virt_latency, vlpsocket.peer_virt_loc,
                         vlpsocket.name)

    def send_int(self, n: int, size: int) -> None:
        """
        Send a positive integer.

        Args:
            n: the integer to be sent.
            size: number of bytes which are used to represent the integer.

        """
        self.sendall(n.to_bytes(size, "big"))

    def recv_int(self, size: int) -> int:
        """
        Receive a positive integer.

        Args:
            size: number of bytes which are used to represent the integer.

        """
        return int.from_bytes(self.recv_exact(size), "big")

    def send_address(self, addr: Tuple[str, int]) -> None:
        """Send an address."""

        # None is allowed.
        if addr is None:
            self.send_int(0, Protocol.HOSTNAME_LEN_FSZ)
            return

        hostname, port = addr
        assert len(hostname) <= Protocol.MAX_HOSTNAME_LEN

        # convert the address to bytes, then send it
        self.sendall(
            len(hostname).to_bytes(Protocol.HOSTNAME_LEN_FSZ, "big") +
            hostname.encode() +
            port.to_bytes(2, "big")
        )

    def recv_address(self) -> Optional[Tuple[str, int]]:
        """Receive an address."""

        # receive hostname's length
        hostname_len = self.recv_int(Protocol.HOSTNAME_LEN_FSZ)

        # "hostname's length equals 0" means "no address".
        if hostname_len == 0:
            return None

        # receive hostname
        hostname = self.recv_exact(hostname_len).decode()

        # receive port and return
        port = self.recv_int(2)
        return hostname, port

    def send_transaction(self, tx: Transaction) -> None:
        """Send a transaction."""
        self.sendall(tx.to_bytes())

    def recv_transaction(self) -> Transaction:
        """Receive a transaction."""
        with self.s.makefile("rb", buffering=0) as f:
            return Transaction.read_from(f)

    def send_block(self, block: Block) -> None:
        """Send a block."""
        self.sendall(block.to_bytes())

    def recv_block(self) -> Block:
        """Receive a block."""
        with self.s.makefile("rb", buffering=0) as f:
            return Block.read_from(f)

    def inform(self, data1, data2) -> None:
        """Send `data1`, optionally followed by `data2`."""
        self.sendall(data1)
        response = self.recv_exact(Protocol.TYPE_CODE_FSZ)
        if response == Protocol.REP_PROCEED:
            self.sendall(data2)
        else:
            assert response == Protocol.REP_STOP
