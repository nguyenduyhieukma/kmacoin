"""
`systemfreezer` is a fork of `lazyminer` (the honest miner).

`systemfreezer` only mines empty blocks and builds its own branch. If
`systemfreezer` has more than 50% power, no transaction can be confirmed and
the whole system is freezed.

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


class SystemFreezer(Thread):
    """This class represents a system freezer."""
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
        """Similar to `Miner.attempt`, but this method is expected to finish in
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
        height: int = 0
        tmp_block: Block = Block(HASH_OF_NULL)
        latest_state = ExtendedState()  # the oldest (highest age) state
        found = True  # indicates if a block was found by this miner last turn
        reward: int  # the reward for each valid block found

        while True:

            # no need to check for blocks mined by others
            if found:
                reward = latest_state.reward
                reward_tx = Transaction(input_ids=[], outputs=[
                    Coin(
                        owner=self.node.owner,
                        value=reward
                    )])
                tmp_block.add_transaction(reward_tx)

            # check for new transactions
            while True:
                if len(tmp_block.txs) == Block.MAX_TXS:
                    break
                try:
                    tx = self.node.tx_queue.get(block=False)

                    # if the transaction is valid, broadcast it but don't add
                    # it to the block being mined.
                    latest_state.process_transaction(tx)
                    self.node.valid_obj_queue.put(tx)

                except Empty:  # the transaction queue is empty
                    break
                except TransactionError:  # current transaction is invalid
                    continue  # just move on

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

                # immediately put `tmp_block` to the block queue
                self.node.block_queue.put(tmp_block)

                # prepare to mine a new block
                height += 1
                latest_state.process_transaction(tmp_block.txs[0],
                                                 check_balance=False)
                latest_state.latest_id = tmp_block.get_id()
                latest_state.latest_timestamp = tmp_block.timestamp
                latest_state.grow()
                tmp_block = Block(tmp_block.get_id())


# fake
LazyMiner = SystemFreezer
