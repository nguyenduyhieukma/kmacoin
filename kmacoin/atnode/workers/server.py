from kmacoin.objects.block import Block
from kmacoin.objects.transaction import Transaction
from kmacoin.network.kmasocket import KMASocket
from kmacoin.network.protocol import Protocol
from kmacoin.atnode.node import Node
from kmacoin.atnode.structures.pool import ObjectNotFound
from kmacoin.atnode.workers.client import Client

from threading import Thread

import os


class XObject(object):
    """
    A wrapper of a transaction, block or address, adding some metadata to be
    passed to node workers.

    For example: `typecode` helps an address processor know if an address came
    with a INF_ADDR or REQ_SWAP_ROLES message; `server thread` allows a
    broadcaster to not relay an object to the node where the object came from.

    Attributes:
        obj: an object which is wrapped.
        typecode: the type of a message which the object is sent with.
        server_thread: a server thread which has received the message/object.

    """
    def __init__(self, obj: object, typecode: int = None,
                 server_thread: 'Server' = None):
        self.obj = obj
        self.typecode = typecode
        self.server_thread = server_thread

    def __getattr__(self, name):
        return getattr(self.obj, name)


class Server(Thread):
    """
    This class represents a server in KMA-Coin system.

    Attributes:
        node: a node which it works for.
        s: a socket which is used to communicate with a remote client.
        allow_swap_roles: indicates whether or not to accept a REQ_SWAP_ROLES
            message.
        allow_req_token: indicates whether or not to accept a REQ_TOKEN
            message.
        partner: a local client thread holding another connection to a same
            node.

    """
    def __init__(self, node: Node, s: KMASocket, allow_swap_roles: bool,
                 allow_req_token: bool):
        super().__init__()
        self.node = node
        self.s = s
        self.allow_swap_roles = allow_swap_roles
        self.allow_req_token = allow_req_token
        self.partner = None

    def run(self):
        try:
            while True:
                # get the message type code
                msg_type_code = self.s.recv_exact(Protocol.TYPE_CODE_FSZ)

                # call appropriate handler
                if msg_type_code == Protocol.PING:
                    self.process_ping()
                elif msg_type_code == Protocol.REQ_TOKEN:
                    self.process_req_token()
                elif msg_type_code == Protocol.REQ_SWAP_ROLES:
                    self.process_req_swap_roles()
                    return
                elif msg_type_code == Protocol.INF_ADDR:
                    self.process_inf_address()
                elif msg_type_code == Protocol.INF_TRANSACTION:
                    self.process_inf_transaction()
                elif msg_type_code == Protocol.INF_BLOCK:
                    self.process_inf_block()
                elif msg_type_code == Protocol.REQ_BLOCK:
                    self.process_req_block()
                elif msg_type_code == Protocol.REQ_BLOCKS:
                    self.process_req_blocks()
                elif msg_type_code == Protocol.REQ_ADDR_LIST:
                    self.process_req_addr_list()
                else:
                    assert False  # unknown message type code -> abort

                self.allow_swap_roles = False  # allow at 1st message only

        except (OSError, AssertionError):
            self.s.close()
            self.node.peers_smp.release()

    def process_ping(self):
        """Process a PING message."""
        self.s.sendall(Protocol.PONG)

    def process_req_token(self):
        """Process a REQ_TOKEN message."""
        if not self.allow_req_token:
            assert False  # not allowed -> abort

        # generate a random token until a unique one is found
        token = os.urandom(Protocol.TOKEN_FSZ)
        while not self.node.token_pool.add(token, self):
            token = os.urandom(Protocol.TOKEN_FSZ)

        # send the token
        self.s.sendall(token)

        # don't allow the client to request another token
        self.allow_req_token = False

    def process_req_swap_roles(self):
        """Process a REQ_SWAP_ROLES message."""
        if not self.allow_swap_roles:
            assert False  # not allowed -> abort

        # get and validate the token
        token = self.s.recv_exact(Protocol.TOKEN_FSZ)
        try:
            server_thread = self.node.token_pool.pop(token)
        except ObjectNotFound:
            assert False  # token not in pool -> abort

        addr = self.s.recv_address()
        if addr:
            if not self.node.add_connected_address(addr):
                assert False  # already connected -> abort

            # put the address to queue to be broadcasted later
            self.node.addr_queue.put(XObject(
                    obj=addr,
                    typecode=Protocol.REQ_SWAP_ROLES,
                    server_thread=server_thread
            ))

        # spawn a client
        self.s.sendall(Protocol.REP_PROCEED)
        Client(self.node, self.s, addr, server_thread).start()

        if self.node.verbose:
            print("\nAdded peer at: {}.".format(addr if addr else "Unknown"))

    def process_inf_address(self):
        """Process a INF_ADDRESS message."""
        addr = self.s.recv_address()
        if addr and self.node.addr_pool.add(addr):
            self.node.addr_queue.put(XObject(
                    obj=addr,
                    typecode=Protocol.INF_ADDR,
                    server_thread=self
            ))

    def process_inf_transaction(self):
        """Process a INF_TRANSACTION message."""
        tx_id = self.s.recv_exact(Transaction.TX_ID_FSZ)

        # if new transaction ID -> receive the transaction then put to queue
        if self.node.tx_id_pool.add(tx_id):
            self.s.sendall(Protocol.REP_PROCEED)
            self.node.tx_queue.put(XObject(
                    obj=self.s.recv_transaction(),
                    typecode=Protocol.INF_TRANSACTION,
                    server_thread=self
            ))

        # if transaction ID already received -> send REP_STOP
        else:
            self.s.sendall(Protocol.REP_STOP)

    def process_inf_block(self):
        """Process a INF_BLOCK message."""
        block_id = self.s.recv_exact(Block.ID_FSZ)

        # if new block ID -> receive the block then put to queue
        if self.node.block_id_pool.add(block_id):
            self.s.sendall(Protocol.REP_PROCEED)
            self.node.block_queue.put(XObject(
                    obj=self.s.recv_block(),
                    typecode=Protocol.INF_BLOCK,
                    server_thread=self
            ))

        # if block ID already received -> send REP_STOP
        else:
            self.s.sendall(Protocol.REP_STOP)

    def process_req_block(self):
        """Process a REQ_BLOCK message."""
        block_id = self.s.recv_exact(Block.ID_FSZ)
        try:
            self.s.sendall(self.node.load_block_data(block_id))
        except FileNotFoundError:
            assert False

    def process_req_blocks(self):
        """Process a REQ_BLOCKS message."""

        # receive client's block height
        height = self.s.recv_int(Protocol.BLOCK_HEIGHT_FSZ)

        # collect the block IDS
        to_be_sent_ids = self.node.block_tree.main_branch.block_ids[
                         height + 1: height + 1 + Protocol.MAX_BLOCKS]

        # send the blocks
        self.s.send_int(len(to_be_sent_ids), Protocol.BLOCK_LIST_LEN_FSZ)
        for block_id in to_be_sent_ids:
            self.s.sendall(self.node.load_block_data(block_id))

    def process_req_addr_list(self):
        """Process a REQ_ADDR_LIST message."""

        # get current addresses
        lst = list(self.node.unconnected_addrs | self.node.connected_addrs)

        # send the number of addresses to be sent
        self.s.send_int(
            min(len(lst), Protocol.MAX_ADDRS),
            Protocol.ADDR_LIST_LEN_FSZ
        )

        # send the addresses
        for addr in lst[:Protocol.MAX_ADDRS]:
            self.s.send_address(addr)
