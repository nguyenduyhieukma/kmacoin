from kmacoin.globaldef.hash import HASH_SIZE
from kmacoin.network.kmasocket import KMASocket
from kmacoin.network.protocol import Protocol
from kmacoin.objects.xstate import BlockError
from kmacoin.atnode.workers.addressprocessor import AddressProcessor
from kmacoin.atnode.workers.blockprocessor import BlockProcessor
from kmacoin.atnode.workers.broadcaster import Broadcaster
from kmacoin.atnode.workers.listener import Listener
from kmacoin.atnode.workers.peeradder import PeerAdder
from kmacoin.atnode.workers.branchbuilder import BranchBuilder
from kmacoin.atnode.node import Node

from threading import Thread

import os
import random


class NodeLauncher(Thread):
    """A node launcher makes everything ready for a node to begin to work.

    What it does:
        - synchronizes with other nodes.
        - spawns workers.

    """

    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        # resume current state (if the node had joined the network earlier)
        path = os.path.join(self.node.data_dir, Node.BLOCK_ID_FILENAME)
        if os.path.isfile(path):

            if self.node.verbose:
                print("\nFetching local block data...")

            i = 0
            with open(path, "rb") as f:
                try:
                    while True:
                        block_id = f.read(HASH_SIZE)
                        if not block_id:
                            break
                        block = self.node.load_block(block_id)
                        self.node.add_block(block, save_block=False)
                        i += 1
                except (FileNotFoundError, AssertionError):
                    if self.node.verbose:
                        print("[ERROR] The data directory is corrupted!")
                    return

            if self.node.verbose:
                print("{} blocks have been added!".format(i))

        # synchronize with other nodes
        if not self.node.unconnected_addrs:
            if self.node.verbose:
                print("\nNo initial peer address given!")
                print("This node is currently the only one in the network!")

        else:
            i = 0
            while True:
                i += 1

                # initialize a socket
                s = KMASocket(virt_loc=self.node.virt_loc, name=self.node.name)
                s.settimeout(self.node.connection_timeout)

                # get a random address
                addr = random.sample(self.node.unconnected_addrs, 1)[0]
                if self.node.verbose:
                    print("\nTry to synchronize with {}".format(addr))

                try:
                    # connect and send a REQ_BLOCKS message
                    s.connect(addr)
                    s.sendall(Protocol.REQ_BLOCKS)
                    s.send_int(self.node.block_tree.get_height(),
                               Protocol.BLOCK_HEIGHT_FSZ)

                    n = s.recv_int(Protocol.BLOCK_LIST_LEN_FSZ)
                    if n == 0:
                        # Block chain synchronization completes!
                        # Now, add more KMA-Coin server addresses.
                        s.sendall(Protocol.REQ_ADDR_LIST)
                        n = s.recv_int(Protocol.ADDR_LIST_LEN_FSZ)
                        j = 0
                        for _ in range(n):
                            if self.node.add_unconnected_address(
                                    s.recv_address()):
                                j += 1

                        if self.node.verbose:
                            print("{} addresses added!".format(j))
                            print("Synchronization completes!")

                        break

                    # receive the blocks
                    if self.node.verbose:
                        print("Adding {} blocks...".format(n))

                    for _ in range(n):
                        self.node.add_block(s.recv_block())

                except (OSError, AssertionError, BlockError):
                    # Something wrong happened!
                    if self.node.verbose:
                        print("[WARNING] Error synchronizing with {}".
                              format(addr))
                    self.node.unconnected_addrs.remove(addr)
                    if self.node.unconnected_addrs:
                        continue

                    # Now, there is no more address to try!
                    if self.node.verbose:
                        print("\nNo more peer to try!")
                        print("[ERROR] Synchronization failed!")
                    return

                finally:
                    s.close()

        if self.node.verbose:
            latest_state = self.node.get_latest_state()
            print("\nCurrent block tree height: {}.".format(latest_state.age))
            print("Current block reward: {} KMAC.".format(
                latest_state.reward))
            print("Current threshold: {}...".format(
                latest_state.threshold.hex()[:self.node.hexlen]))

        # spawn workers
        AddressProcessor(self.node).start()
        BlockProcessor(self.node).start()
        BranchBuilder(self.node).start()
        Broadcaster(self.node).start()
        PeerAdder(self.node).start()
        Listener(self.node).start()

        cmd = "global LazyMiner; " \
              "from kmacoin.atnode.workers.miners.{} import LazyMiner".format(
            self.node.miner_module)
        exec(cmd)
        LazyMiner(self.node).start()
