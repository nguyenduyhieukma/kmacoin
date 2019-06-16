from kmacoin.network.protocol import Protocol
from kmacoin.network.kmasocket import KMASocket
from kmacoin.atnode.node import Node

from threading import Thread
from typing import Tuple


class AddressProcessor(Thread):
    """This class represents an address processor in KMA-Coin system."""
    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        while True:
            # get the address
            xaddr = self.node.addr_queue.get()
            addr = xaddr.obj

            if xaddr.typecode == Protocol.REQ_SWAP_ROLES:
                # address came with REQ_SWAP_ROLES message
                if self.validate(addr):
                    self.node.valid_obj_queue.put(xaddr)

            else:  # address came with INF_ADDRESS message
                if addr in self.node.unconnected_addrs:
                    continue
                if addr in self.node.connected_addrs:
                    continue
                if not self.validate(addr):
                    continue
                if self.node.add_unconnected_address(addr):
                    self.node.valid_obj_queue.put(xaddr)

    def validate(self, addr: Tuple[str, int]) -> bool:
        """
        Validate an address.

        Notes: this method will try to connect to the address and send a PING
        message.

        Args:
            addr: the address to be validated.

        Returns:
            True if the address is valid (nothing wrong happened).

        """
        s = KMASocket(virt_loc=self.node.virt_loc, name=self.node.name)
        s.settimeout(self.node.connection_timeout)

        try:
            s.connect(addr)
            s.sendall(Protocol.PING)
            assert s.recv_exact(Protocol.TYPE_CODE_FSZ) == Protocol.PONG
            return True
        except (OSError, AssertionError):
            return False
        finally:
            s.close()
