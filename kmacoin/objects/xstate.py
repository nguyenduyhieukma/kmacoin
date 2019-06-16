from kmacoin.globaldef.mining import *
from kmacoin.globaldef.hash import HASH_OF_NULL, HASH_SIZE
from kmacoin.objects.state import State, TransactionError
from kmacoin.objects.block import Block

import time
import copy


class BlockError(Exception):
    """
    Raised when an invalid block is processed.

    Attributes:
        code: a type code indicates why the block is invalid.
        block: the invalid block.
        additional_info: more information on the error.

    """

    # All error codes:
    INVALID_TIMESTAMP = 0
    INVALID_NONCE = 1
    INVALID_PREV_ID = 2
    INVALID_TX_COUNT = 3
    INVALID_TX = 4
    UNBALANCE = 5

    def __init__(self, msg: str, code: int, block: Block, **kwargs):
        super().__init__(msg)
        self.code = code
        self.block = block
        self.additional_info = kwargs


class ExtendedState(State):
    """
    A state's subclass, supporting block-based transition.

    Attributes:
        age: the number of blocks the state has processed.
        reward: the current block reward.
        threshold: the current threshold.
        latest_id: ID of the latest block processed by the state.
        latest_timestamp: timestamp of the latest block processed by the state.
        last_threshold_update: the last time the state's threshold is updated.

    """
    age: int
    reward: int
    threshold: bytes

    def __init__(self):
        super().__init__()
        self.age = 0
        self.reward = INIT_REWARD
        self.threshold = INIT_THRESHOLD
        self.latest_id = HASH_OF_NULL
        self.latest_timestamp = 0
        self.last_threshold_update = None

    def process_block(self, block: Block) -> None:
        """
        Process a block and let this state transit.

        Args:
            block: the block to be processed.

        Raises:
            BlockError: when the block is invalid

        """
        assert self.latest_id == block.prev_id

        # check timestamp
        if not self.latest_timestamp <= block.timestamp <= int(time.time()):
            raise BlockError(
                "Invalid timestamp!",
                BlockError.INVALID_TIMESTAMP,
                block
            )

        # check nonce
        if not block.get_id() < self.threshold:
            raise BlockError(
                "Invalid nonce!",
                BlockError.INVALID_NONCE,
                block
            )

        # check tx_count
        if len(block.txs) > Block.MAX_TXS:
            raise BlockError(
                "Too many transactions!",
                BlockError.INVALID_TX_COUNT,
                block
            )

        # backup current coins
        coins_bk = copy.deepcopy(self.coins)

        # check each transaction
        total_fee = 0
        for i in range(len(block.txs)):
            tx = block.txs[i]
            try:
                total_fee += self.process_transaction(
                    tx,
                    check_balance=(False if i == 0 else True)
                )
            except TransactionError as err:
                self.coins = coins_bk
                raise BlockError(
                    "Invalid transaction!",
                    BlockError.INVALID_TX,
                    block,
                    index=i,
                    tx_err=err
                )

        # check balance
        if total_fee + self.reward != 0:
            self.coins = coins_bk
            raise BlockError(
                "Block is unbalanced!",
                BlockError.UNBALANCE,
                block
            )

        # update metadata
        self.latest_id = block.get_id()
        self.latest_timestamp = block.timestamp
        self.grow()

    def grow(self) -> None:
        """
        Increment this state's age.

        Notes: this method potentially update the state's current reward and
        threshold.
        """
        self.age += 1

        if self.age == 1:  # first grow ever
            self.last_threshold_update = self.latest_timestamp
            return

        # check whether a threshold update is needed
        if self.age % THRESHOLD_UPDATE_INTERVAL == 1:
            observed_time = self.latest_timestamp - self.last_threshold_update
            expected_time = BLOCK_INTERVAL * THRESHOLD_UPDATE_INTERVAL
            self.threshold = (
                int.from_bytes(self.threshold, "big") *
                observed_time //
                expected_time
            ).to_bytes(HASH_SIZE, "big")
            self.last_threshold_update = self.latest_timestamp

        # check whether a reward update is needed
        if self.age % REWARD_UPDATE_INTERVAL == 0:
            self.reward = self.reward // 2
