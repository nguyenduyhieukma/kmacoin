"""
This module contains initial mining parameters.

These parameters describe various aspects of block-mining in KMA-Coin. They
must be carefully set before the system is deployed, and agreed by all
participants.
"""
from .hash import HASH_SIZE


# How often are blocks announced?
BLOCK_INTERVAL = 5  # seconds.

# What is the initial reward for successfully mining a block?
INIT_REWARD = 1000  # KMAC.

# How often is the block reward halved?
REWARD_UPDATE_INTERVAL = 100  # blocks between 2 consecutive reward updates.

# What is the initial threshold for the hash puzzle?
EXPECTED_TOTAL_HASHRATE = 30  # hashes per second
EXPECTED_HASHES_PER_BLOCK = BLOCK_INTERVAL * EXPECTED_TOTAL_HASHRATE
INIT_THRESHOLD = (2**(HASH_SIZE*8) // EXPECTED_HASHES_PER_BLOCK).to_bytes(
    HASH_SIZE, "big")

# How often is the threshold updated?
THRESHOLD_UPDATE_INTERVAL = 20
