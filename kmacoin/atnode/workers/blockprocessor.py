from kmacoin.globaldef.mining import THRESHOLD_UPDATE_INTERVAL, REWARD_UPDATE_INTERVAL
from kmacoin.objects.xstate import BlockError
from kmacoin.objects.block import Block
from kmacoin.atnode.node import Node

from threading import Thread


class BlockProcessor(Thread):
    """This class represents a block processor."""

    # Command codes
    CMD_EXIT = 0

    def __init__(self, node: Node):
        super().__init__()
        self.node = node

    def run(self):

        while True:
            # get block/command
            obj = self.node.block_queue.get()

            if isinstance(obj, int):  # got a command
                if obj == BlockProcessor.CMD_EXIT:
                    return
                else:
                    assert False

            # obj should be a block now
            block: Block = obj

            # verify and update the block tree
            try:
                if not self.node.add_block(block):
                    continue  # duplicate or orphaned block

                self.node.valid_obj_queue.put(block)

                if self.node.verbose:
                    new_state = self.node.state_cache.get(block.get_id())
                    new_age = new_state.age

                    # print new block info
                    print("\n({}) New block received.".format(new_age))
                    print("Block ID: {}...".
                          format(block.get_id().hex()[:self.node.hexlen]))
                    new_coin = block.txs[0].outputs[0]
                    print("{} KMAC added to account {}...".format(
                        new_coin.value,
                        new_coin.owner.hex()[:self.node.hexlen]
                    ))

                    # check if threshold is updated
                    if (new_age % THRESHOLD_UPDATE_INTERVAL == 1 and
                            new_age != 1):
                        print("\nThreshold updated to {}...".format(
                            new_state.threshold.hex()[:self.node.hexlen]))

                    # check if reward is updated
                    if new_age % REWARD_UPDATE_INTERVAL == 0:
                        print("\nReward updated to {} KMAC.".
                              format(new_state.reward))

            except BlockError as err:
                if self.node.verbose:
                    print("\n[WARNING] Receive an invalid block.")
                    print("Block ID: {}...".
                          format(block.get_id().hex()[:self.node.hexlen]))
                    print("({})".format(err))

                # may add action to ban the node which sent the invalid block...
