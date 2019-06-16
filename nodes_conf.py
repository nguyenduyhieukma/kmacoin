nodes_conf = [
    {
        "VIRTUAL_LOCATION": (3, 3),
        "LISTENING_ADDRESS": ("localhost", 11111),
        "PUBLIC_ADDRESS": ("localhost", 11111),
    },
    {
        "VIRTUAL_LOCATION": (5, 7),
        "LISTENING_ADDRESS": ("localhost", 22222),
        "PUBLIC_ADDRESS": ("localhost", 22222),

        "INITIAL_PEER_ADDRESSES": [
            ("localhost", 11111)
        ],
    },
    {
        "VIRTUAL_LOCATION": (7, 3),
        "INITIAL_PEER_ADDRESSES": [
            ("localhost", 11111)
        ],
    }
]
