from kmacoin.network.kmasocket import KMASocket
from kmacoin.atnode.node import Node
from kmacoin.atnode.workers.server import Server

from threading import Thread


class Listener(Thread):
    """This class represents a listener in KMA-Coin system."""
    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        # no listening address given -> return
        if not self.node.public_addr:
            if self.node.verbose:
                print("\n[WARNING] Listener is not running!")
                print("No listening address given.")
            return

        # create the server socket
        ss = KMASocket(virt_loc=self.node.virt_loc, name=self.node.name)

        # try to bind to the listening address
        try:
            ss.bind(self.node.listening_addr)
            if self.node.verbose:
                print("\nListener is at {}".format(self.node.listening_addr))

        except OSError:
            if self.node.verbose:
                print("\n[WARNING] Listener is not running!")
                print("Cannot bind to {}.".format(self.node.listening_addr))

            ss.close()
            return

        # start listening and accepting incoming connections
        ss.listen()
        while True:
            self.node.peers_smp.acquire()
            client_s, client_addr = ss.accept()
            client_s.settimeout(self.node.peer_timeout)
            Server(
                self.node,
                KMASocket.from_vlpsocket(client_s),
                allow_swap_roles=True,
                allow_req_token=True
            ).start()
