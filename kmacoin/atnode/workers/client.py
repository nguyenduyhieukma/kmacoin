from kmacoin.network.kmasocket import KMASocket
from kmacoin.network.protocol import Protocol
from kmacoin.atnode.node import Node

from typing import Tuple
from threading import Thread
from queue import Queue, Empty


class Client(Thread):
    """
    This class represents a client in KMA-Coin system.

    Attributes:
        node: a node which it works for.
        s: a socket which is used to communicate with a remote server.
        cmd_queue: a queue where the client fetches commands.
        peer_addr: the remote server's address.
        partner: a local server thread holding another connection to a same
            node.

    """

    # Command codes:
    CMD_EXIT = 0
    CMD_SEND = 1
    CMD_INFORM = 2
    CMD_REQ_BLOCK = 3

    def __init__(self, node: Node, s: KMASocket, peer_addr: Tuple[str, int],
                 partner):
        super().__init__()
        self.node = node
        self.s = s

        self.peer_addr = peer_addr
        self.partner = partner
        self.partner.partner = self

        self.cmd_queue = Queue()
        with self.node.client_cmd_queues_cv:
            self.node.client_cmd_queues.add(self.cmd_queue)

    def run(self):
        cmd: int
        q: Queue

        try:
            while True:
                # Look for command
                cmd, *args = self.cmd_queue.get()

                if cmd == Client.CMD_EXIT:
                    assert False
                elif cmd == Client.CMD_SEND:
                    data = args[0]
                    self.s.sendall(data)
                elif cmd == Client.CMD_INFORM:
                    data1, data2 = args
                    self.s.inform(data1, data2)
                elif cmd == Client.CMD_REQ_BLOCK:
                    block_id, q = args
                    self.s.sendall(Protocol.REQ_BLOCK + block_id)
                    q.put(self.s.recv_block())
                else:
                    raise Exception("Unknown client command!")

        except (OSError, AssertionError):
            # release resources
            self.s.close()
            self.node.peers_smp.release()

            # update node's connected address list
            self.node.remove_connected_address(self.peer_addr)

            # clean up node's list of client command queues
            with self.node.client_cmd_queues_cv:
                self.node.client_cmd_queues.remove(self.cmd_queue)
                if len(self.node.client_cmd_queues) < self.node.min_peers:
                    self.node.client_cmd_queues_cv.notify()

            # wake up the thread waiting for the result of last command (if
            # any)
            if cmd == Client.CMD_REQ_BLOCK:
                q.put(None)

            # clean up the client's command queue
            try:
                while True:
                    cmd, *args = self.cmd_queue.get(block=False)
                    if cmd == Client.CMD_REQ_BLOCK:
                        q = args[-1]
                        q.put(None)
            except Empty:
                pass

            if self.node.verbose:
                print("\nDisconnected peer at: {}.".format(
                    self.peer_addr if self.peer_addr else "Unknown"))
