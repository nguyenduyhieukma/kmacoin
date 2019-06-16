"""
`doublespender` is a fork of `lazyminer` (the honest miner).

`doublespender` tries to replace the current longest branch with its own one.
Transactions made in the past may be reversed. This allows `doublespender` to
spend its previously spent coins once more time.

"""
from kmacoin.globaldef.hash import HASH_OF_NULL
from kmacoin.objects.block import Block
from kmacoin.objects.transaction import Transaction
from kmacoin.objects.coin import Coin
from kmacoin.objects.state import TransactionError
from kmacoin.objects.xstate import ExtendedState
from kmacoin.atnode.node import Node

from threading import Thread
from queue import Empty

import os
import time


class DoubleSpender(Thread):
    """This class represents a double spender."""

    # the height of the tree when the attack begins
    START_HEIGHT = 3

    # the number of confirmations needed before private blocks are announced.
    CONFIRMATION_COUNT = 5

    def __init__(self, node: Node, hash_rate=None):
        super().__init__()
        self.node = node
        if not hash_rate:
            hash_rate = self.node.hash_rate
        self.virt_attempt_time_cost = 1.0 / hash_rate
        self.sleep_time = self.virt_attempt_time_cost

        # training the miner
        for _ in range(3):
            self.virt_attempt(Block(HASH_OF_NULL), HASH_OF_NULL)

    def attempt(self, block: Block, threshold: bytes) -> bool:
        """
        Attempt to find a nonce for a block to be valid under given threshold.

        Args:
            block: the temporary block.
            threshold: the given threshold.

        Returns:
            True in case of success, otherwise False.

        """
        block.set_nonce(os.urandom(Block.NONCE_FSZ))
        if block.get_id() < threshold:
            return True
        else:
            return False

    def virt_attempt(self, block: Block, threshold: bytes) -> bool:
        """Similar to `attempt`, but this method is expected to finish in
        a pre-defined amount of time.

        Notes: each call to this method will automatically adjust this miner's
        sleep time for better accuracy at later attempts.
        """
        t1 = time.time()

        # sleep then make a real attempt
        time.sleep(self.sleep_time)
        result = self.attempt(block, threshold)

        t2 = time.time()

        # adjust the sleep time
        self.sleep_time += self.virt_attempt_time_cost - (t2-t1)

        return result

    def run(self):
        height: int = -1
        tmp_block: Block = Block(HASH_OF_NULL)
        latest_state: ExtendedState  # the oldest (highest age) state
        found = False  # indicates if a block was found by this miner last turn
        reward: int  # the reward for each valid block found

        attack: bool = False
        private_blocks = []

        while True:

            # check if attack has done
            if attack:
                if (height > self.node.block_tree.get_height() >
                        (DoubleSpender.START_HEIGHT +
                         DoubleSpender.CONFIRMATION_COUNT)):
                    # done attack
                    attack = False
                    for block in private_blocks:
                        self.node.block_queue.put(block)

            # check if the block tree has grown
            if (not attack and height < self.node.block_tree.get_height()) \
                    or found:

                if not found:  # block found by other miners

                    # pull back transactions in temporary block
                    for tx in tmp_block.txs[1:]:  # exclude `reward_tx`
                        self.node.tx_queue.put(tx)
                    tmp_block.clear_transactions()

                    # get the latest state
                    latest_state = self.node.get_latest_state()
                    tmp_block.prev_id = latest_state.latest_id

                    # update height
                    height = latest_state.age

                # regardless of who found the block,
                # update the reward, add new `reward_tx` to `tmp_block`
                reward = latest_state.reward
                reward_tx = Transaction(input_ids=[], outputs=[
                    Coin(
                        owner=self.node.owner,
                        value=reward
                    )])
                tmp_block.add_transaction(reward_tx)

                if height == DoubleSpender.START_HEIGHT:
                    attack = True

            # check for new transactions
            reward_change = False
            while True:
                if len(tmp_block.txs) == Block.MAX_TXS:
                    break
                try:
                    tx = self.node.tx_queue.get(block=False)
                    fee = latest_state.process_transaction(tx)
                    tmp_block.add_transaction(tx)
                    self.node.valid_obj_queue.put(tx)
                    if fee:
                        reward += fee
                        reward_change = True

                except Empty:  # the transaction queue is empty
                    break
                except TransactionError:  # current transaction is invalid
                    continue  # just move on

            # collect the transaction fee
            if reward_change:
                reward_tx = Transaction(input_ids=[], outputs=[
                    Coin(
                        owner=self.node.owner,
                        value=reward
                    )])
                tmp_block.replace_transaction(0, reward_tx)

            # prepare to mine
            tmp_block.update_timestamp()

            # attempt to find a valid nonce
            found = False
            if self.virt_attempt(tmp_block, latest_state.threshold):  # success

                found = True
                if self.node.verbose:
                    print("\n({}) Successfully mine a block!".
                          format(height + 1))
                    print("Reward: {} KMAC.".format(reward))

                # immediately put `tmp_block` to the block queue (if not in
                # the attack state)
                if not attack:
                    self.node.block_queue.put(tmp_block)
                else:
                    private_blocks.append(tmp_block)

                # prepare to mine a new block
                height += 1
                latest_state.process_transaction(tmp_block.txs[0],
                                                 check_balance=False)
                latest_state.latest_id = tmp_block.get_id()
                latest_state.latest_timestamp = tmp_block.timestamp
                latest_state.grow()
                tmp_block = Block(tmp_block.get_id())


# fake
LazyMiner = DoubleSpender
