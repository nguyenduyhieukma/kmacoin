from kmacoin.objects.block import Block
from kmacoin.network.protocol import Protocol
from kmacoin.atnode.node import Node
from kmacoin.atnode.workers.client import Client
from kmacoin.atnode.workers.server import XObject

from threading import Thread
from queue import Queue
from typing import Union


class BranchBuilder(Thread):
    """This class represents a branch builder."""
    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        tmp_q = Queue()
        while True:
            # get an orphaned block
            orphaned_block: Union[XObject, Block] = \
                self.node.orphan_queue.get()

            # take the command queue of the client which holds the connection
            # to the node which sent the orphaned block
            server_thread = orphaned_block.server_thread
            client_thread = server_thread.partner
            cmd_q = client_thread.cmd_queue

            branch = [orphaned_block]

            # get the orphaned block's previous block until we can connect the
            # branch to the block tree.
            while not self.node.block_tree.has_block(orphaned_block.prev_id):

                with self.node.client_cmd_queues_cv:
                    if cmd_q not in self.node.client_cmd_queues:
                        # broken link
                        branch = []
                        break
                    else:
                        cmd_q.put([Client.CMD_REQ_BLOCK,
                                   orphaned_block.prev_id, tmp_q])

                # get previous block
                block = tmp_q.get()
                if not block:  # broken link
                    branch = []
                    break
                self.node.block_id_pool.add(block.get_id())

                # update the branch
                orphaned_block = XObject(block, Protocol.REQ_BLOCK,
                                         server_thread)
                branch.append(orphaned_block)

            # push branch's blocks to the block queue
            for block in branch[::-1]:
                self.node.block_queue.put(block)
