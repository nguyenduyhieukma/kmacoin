DEFAULT_NODE_CONFIG = {

    "INITIAL_PEER_ADDRESSES": [],

    "LISTENING_ADDRESS": None,
    "PUBLIC_ADDRESS": None,

    "TRANSACTION_ID_POOL_SIZE": 20,
    "BLOCK_ID_POOL_SIZE": 5,
    "ADDRESS_POOL_SIZE": 10,
    "TOKEN_POOL_SIZE": 10,

    "MINER_MODULE": "lazyminer",  # the module to import `LazyMiner` from
    "HASH_RATE": 10,  # hashes per second

    "PEERS_RANGE": (2, 10),

    "CONNECTION_TIMEOUT": 10,  # seconds
    "PEER_TIMEOUT": 300,  # seconds

    "VERBOSE": True,
    "HEX_STRING_LENGTH": 15  # characters
}
