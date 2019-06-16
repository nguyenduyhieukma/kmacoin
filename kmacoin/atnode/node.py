from kmacoin.globaldef.hash import HASH_OF_NULL
from kmacoin.objects.block import Block
from kmacoin.objects.xstate import ExtendedState
from kmacoin.atnode.structures.pool import Pool
from kmacoin.atnode.structures.statecache import StateCache
from kmacoin.atnode.structures.blocktree import BlockTree

from typing import Dict, Any, Tuple
from queue import Queue
from threading import Lock, Condition, Semaphore

import copy
import random
import os


class Node(object):
    """
    This class represents a node in KMA-Coin system.

    Attributes:
        state_cache: the cache of recently used states.

        block_tree: the block tree represented by a list of list of block IDs
            of a same height.
        block_tree_lock: a lock must be acquired before update the block tree.
        vis_block_q: a block queue which is used to send blocks to the block
            tree visualizer

        unconnected_addrs: the unconnected KMA-Coin server address list.
        connected_addrs: the connected KMA-Coin server address list.
        addrs_cv: a condition variable, synchronizing accesses to the two
            address lists. Every thread must acquire this before updates one
            of the two lists. Furthermore, when `len(unconnected_addrs)`
            changes from 0 to 1, `notify` on this variable needs to be called
            to wake up threads sleep when `unconnected_addrs` is empty.

        name: the node's name
        virt_loc: the node's virtual location

        listening_addr: listening address of the node's listener
        public_addr: the node's listening address as seen from the outside.

        data_dir: where the node stores its data.

        tx_id_pool: a set of recently received transaction IDs.
        block_id_pool: a set of recently received block IDs.
        addr_pool: a set of recently received addresses.
        token_pool: a set of recently given tokens.

        tx_queue: the transaction queue.
        block_queue: the block queue.
        addr_queue: the address queue.
        valid_obj_queue: the valid object queue.
        orphan_queue: the queue of orphaned blocks

        client_cmd_queues: a list of client command queues.
        client_cmd_queues_cv: a condition variable, synchronizing accesses to
            `client_cmd_queues`. `notify` on this variable needs to be called
            when `len(client_cmd_queues)` below the minimum number of peers
            required.

        miner_module: the module to import `LazyMiner` from.
        hash_rate: expected hashes performed per second.
        owner: an account where reward coins go to.

        min_peers: the minimum number of peers required.
        max_peers: the maximum number of peers required.
        peers_smp: a semaphore, used to limit the number of peers.

        connection_timeout: timeout value for connection establishment.
        peer_timeout: timeout value for peer link inactivity.

        verbose: indicates whether workers should print out useful info.
        hexlen: maximum hex string length.

    """

    # This parameter decides the state cache's size:
    STATE_CACHE_SIZE = 5

    # This parameter decides the data directory tree's height:
    DIR_DEPTH = 2

    # Name of the file where block IDs are stored.
    BLOCK_ID_FILENAME = "block_ids.data"

    def __init__(self, conf: Dict[str, Any]):
        """
        Node constructor.

        Args:
            conf: contains configuration settings for the new node.

        """
        self.state_cache = StateCache(Node.STATE_CACHE_SIZE)
        self.state_cache.add(HASH_OF_NULL, ExtendedState())

        self.block_tree = BlockTree()
        self.block_tree_lock = Lock()
        self.vis_block_q = None

        self.unconnected_addrs = set(conf["INITIAL_PEER_ADDRESSES"])
        self.connected_addrs = set()
        self.addrs_cv = Condition()

        self.name = conf["NAME"]
        self.virt_loc = conf["VIRTUAL_LOCATION"]

        self.listening_addr = conf["LISTENING_ADDRESS"]
        self.public_addr = conf["PUBLIC_ADDRESS"]
        self.connected_addrs.add(self.public_addr)

        self.data_dir = conf["DATA_DIRECTORY"]

        self.tx_id_pool = Pool(conf["TRANSACTION_ID_POOL_SIZE"])
        self.block_id_pool = Pool(conf["BLOCK_ID_POOL_SIZE"])
        self.addr_pool = Pool(conf["ADDRESS_POOL_SIZE"])
        self.token_pool = Pool(conf["TOKEN_POOL_SIZE"])

        self.tx_queue = Queue()
        self.block_queue = Queue()
        self.addr_queue = Queue()
        self.valid_obj_queue = Queue()
        self.orphan_queue = Queue()

        self.client_cmd_queues = set()
        self.client_cmd_queues_cv = Condition()

        self.miner_module = conf["MINER_MODULE"]
        self.hash_rate = conf["HASH_RATE"]
        self.owner = bytes.fromhex(conf["OWNER_ACCOUNT"])

        self.min_peers, self.max_peers = conf["PEERS_RANGE"]
        self.peers_smp = Semaphore(self.max_peers * 2)

        self.connection_timeout = conf["CONNECTION_TIMEOUT"]
        self.peer_timeout = conf["PEER_TIMEOUT"]

        self.verbose = conf["VERBOSE"]
        self.hexlen = conf["HEX_STRING_LENGTH"]

    def add_unconnected_address(self, addr: Tuple[str, int]) -> bool:
        """
        Add an address to the node's unconnected address list.

        Notes: this method is thread-safe.

        Args:
            addr: the address to be added.

        Returns:
            True if actually added.

        """
        with self.addrs_cv:
            if addr not in self.connected_addrs:
                if addr not in self.unconnected_addrs:
                    self.unconnected_addrs.add(addr)
                    self.addrs_cv.notify()
                    return True

            return False

    def add_connected_address(self, addr: Tuple[str, int]) -> bool:
        """
        Add an address to the node's connected address list.

        Notes: This method is thread-safe.

        Args:
            addr: the address to be added.

        Returns:
            True if actually added.

        """
        with self.addrs_cv:
            if addr in self.unconnected_addrs:
                self.unconnected_addrs.remove(addr)

            if addr not in self.connected_addrs:
                self.connected_addrs.add(addr)
                return True

            return False

    def remove_connected_address(self, addr: Tuple[str, int]) -> bool:
        """
        Try to remove an address from the connected address list.

        Notes: this method is thread-safe.

        Args:
            addr: the address to be removed.

        Returns:
            True if the address is actually removed, otherwise False.
        """
        with self.addrs_cv:
            if addr in self.connected_addrs:
                self.connected_addrs.remove(addr)
                return True
            return False

    def pop_random_unconnected_address(self) -> Tuple[str, int]:
        """
        Pop a random unconnected address.

        Notes: caller thread is blocked if the list is empty. This method is
        thread-safe.

        Returns:
            An unconnected address.

        """
        with self.addrs_cv:
            while len(self.unconnected_addrs) == 0:
                self.addrs_cv.wait()
            addr = random.sample(self.unconnected_addrs, 1)[0]
            self.unconnected_addrs.remove(addr)
            return addr

    def get_block_path(self, block_id: bytes, make_dir: bool = True) -> str:
        """Return the path where a block is or to be stored."""
        block_id_h = block_id.hex()
        dirname = os.path.join(
            self.data_dir,
            *[
                block_id_h[i:i+2] for i in
                range(len(block_id_h) - 2*Node.DIR_DEPTH, len(block_id_h), 2)
            ],
        )
        if make_dir:
            os.makedirs(dirname, exist_ok=True)

        return os.path.join(dirname, block_id_h[:-2 * Node.DIR_DEPTH])

    def save_block_data(self, block_data: bytes, block_id: bytes) -> None:
        """Save block data, given its ID."""
        with open(self.get_block_path(block_id), "wb") as f:
            f.write(block_data)

    def load_block_data(self, block_id: bytes) -> bytes:
        """Load block data, given block ID."""
        with open(self.get_block_path(block_id, make_dir=False), "rb") as f:
            return f.read()

    def save_block(self, block: Block) -> None:
        """Save a block to the data directory."""

        # save block data
        self.save_block_data(block.to_bytes(), block.get_id())

        # save block ID
        with open(os.path.join(self.data_dir, Node.BLOCK_ID_FILENAME),
                  "ab") as f:
            f.write(block.get_id())

    def load_block(self, block_id: bytes) -> Block:
        """Load a block, given its ID."""
        with open(self.get_block_path(block_id, make_dir=False), "rb") as f:
            return Block.read_from(f)

    def add_block(self, block: Block, save_block: bool = True) -> bool:
        """
        Add a block to this node's block tree.

        Warnings: This method is not thread-safe and should only be called
        by one thread.

        Args:
            block: the block to be added.
            save_block: True if the block needs to be saved.

        Raises:
            BlockError: if the block is invalid.

        Returns:
            True if the block is actually added.

        """

        # check duplicate block
        if self.block_tree.has_block(block.get_id()):
            return False  # simply return

        # check orphaned block
        if not self.block_tree.has_block(block.prev_id):
            self.orphan_queue.put(block)
            return False

        # validate/process received block
        state = self.get_state(block.prev_id)
        state.process_block(block)

        # update state cache
        self.state_cache.add(block.get_id(), state)

        # update block tree
        with self.block_tree_lock:
            self.block_tree.add(block.get_id(), block.prev_id)

            # push the block to the block tree visualizer
            if self.vis_block_q:
                self.vis_block_q.put((block.get_id(), block.prev_id,
                                      block.txs[0].outputs[0].owner.hex()))

        # save the block if required
        if save_block:
            self.save_block(block)

        return True

    def get_state(self, block_id: bytes) -> ExtendedState:
        """Get the state after process a block, given the block ID."""
        if self.state_cache.haskey(block_id):
            state = copy.deepcopy(self.state_cache.get(block_id))
        else:
            # the block is old, the state after has been removed from cache.
            state = ExtendedState()
            for bid in self.block_tree.get_path(block_id):
                if bid == HASH_OF_NULL:
                    continue
                state.process_block(self.load_block(bid))

        return state

    def get_latest_state(self) -> ExtendedState:
        """Get a deep copy of the latest state."""
        latest_id = self.block_tree.get_top_block()
        return self.get_state(latest_id)
