from kmacoin.objects.block import Block
from kmacoin.objects.transaction import Transaction
from kmacoin.network.protocol import Protocol
from kmacoin.atnode.node import Node
from kmacoin.atnode.workers.server import XObject
from kmacoin.atnode.workers.client import Client

from typing import Tuple
from threading import Thread
from queue import Queue

import random


class Broadcaster(Thread):
    """This class represents a broadcaster in KMA-Coin system."""
    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):
        while True:
            # get an object
            received_obj = self.node.valid_obj_queue.get()

            # classify the object
            if isinstance(received_obj, XObject):
                if isinstance(received_obj.obj, Transaction):
                    self.broadcast_transaction(
                        received_obj.obj,
                        received_obj.server_thread.partner.cmd_queue
                    )
                elif isinstance(received_obj.obj, Block):
                    self.broadcast_block(
                        received_obj.obj,
                        received_obj.server_thread.partner.cmd_queue
                    )
                elif isinstance(received_obj.obj, Tuple):
                    self.broadcast_address(
                        received_obj.obj,
                        received_obj.server_thread.partner.cmd_queue
                    )
                else:
                    assert False

            elif isinstance(received_obj, Block):
                # a block created by the node's miner
                block = received_obj
                self.node.block_id_pool.add(block.get_id())
                self.broadcast_block(block)

            else:
                assert False

    def broadcast_address(self, addr: Tuple[str, int], exclude: Queue = None) \
            -> None:
        """Broadcast an address."""

        # convert the address to bytes
        hostname, port = addr
        addr_data = (
            Protocol.INF_ADDR +
            len(hostname).to_bytes(Protocol.HOSTNAME_LEN_FSZ, "big") +
            hostname.encode() +
            port.to_bytes(2, "big")
        )

        # broadcast to at most 2 other nodes
        with self.node.client_cmd_queues_cv:
            for cmd_queue in random.sample(
                self.node.client_cmd_queues,
                min(2, len(self.node.client_cmd_queues))
            ):
                if cmd_queue == exclude:
                    continue
                cmd_queue.put([Client.CMD_SEND, addr_data])

    def broadcast_transaction(self, tx: Transaction, exclude: Queue = None) \
            -> None:
        """Broadcast a transaction."""
        data1 = Protocol.INF_TRANSACTION + tx.get_id()
        data2 = tx.to_bytes()

        with self.node.client_cmd_queues_cv:
            for cmd_queue in self.node.client_cmd_queues:
                if cmd_queue == exclude:
                    continue
                cmd_queue.put([Client.CMD_INFORM, data1, data2])

    def broadcast_block(self, block: Block, exclude: Queue = None) -> None:
        """Broadcast a block."""
        data1 = Protocol.INF_BLOCK + block.get_id()
        data2 = block.to_bytes()

        with self.node.client_cmd_queues_cv:
            for cmd_queue in self.node.client_cmd_queues:
                if cmd_queue == exclude:
                    continue
                cmd_queue.put([Client.CMD_INFORM, data1, data2])
