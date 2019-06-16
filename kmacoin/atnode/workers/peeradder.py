from kmacoin.network.kmasocket import KMASocket
from kmacoin.network.protocol import Protocol
from kmacoin.atnode.node import Node
from kmacoin.atnode.workers.server import Server
from kmacoin.atnode.workers.client import Client

from threading import Thread


class PeerAdder(Thread):
    """This class represents a peer adder in KMA-Coin system."""
    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        while True:

            # wait until the number of peers is less than required
            with self.node.client_cmd_queues_cv:
                while len(self.node.client_cmd_queues) >= self.node.min_peers:
                    self.node.client_cmd_queues_cv.wait()

            # get an unconnected address
            addr = self.node.pop_random_unconnected_address()

            # acquire the semaphore 2 times to create 2 sockets.
            self.node.peers_smp.acquire()
            self.node.peers_smp.acquire()
            s1 = KMASocket(virt_loc=self.node.virt_loc, name=self.node.name)
            s2 = KMASocket(virt_loc=self.node.virt_loc, name=self.node.name)
            s1.settimeout(self.node.connection_timeout)
            s2.settimeout(self.node.connection_timeout)

            # try to connect
            try:
                s1.connect(addr)
                s2.connect(addr)

                # turn `s1` into server-side socket
                s2.sendall(Protocol.REQ_TOKEN)
                token = s2.recv_exact(Protocol.TOKEN_FSZ)
                s1.sendall(Protocol.REQ_SWAP_ROLES + token)
                s1.send_address(self.node.public_addr)
                response = s1.recv_exact(Protocol.TYPE_CODE_FSZ)
                assert response == Protocol.REP_PROCEED

                # spawn a server and a client for this new peer link
                s1.settimeout(self.node.peer_timeout)
                s2.settimeout(self.node.peer_timeout)
                server_thread = Server(self.node, s1, allow_swap_roles=False,
                                       allow_req_token=False)
                server_thread.start()
                Client(self.node, s2, addr, server_thread).start()

                # update the connected address list
                assert self.node.add_connected_address(addr)

                if self.node.verbose:
                    print("\nAdded peer at {}.".format(addr))

            except (OSError, AssertionError):
                s1.close()
                s2.close()
                self.node.peers_smp.release()
                self.node.peers_smp.release()
