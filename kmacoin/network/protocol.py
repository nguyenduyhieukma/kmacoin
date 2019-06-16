class Protocol(object):
    """This class acts as a namespace."""

    # Message type code field size:
    TYPE_CODE_FSZ = 1

    # All client-to-server message type codes:
    PING = b"\x00"
    REQ_TOKEN = b"\x01"
    REQ_SWAP_ROLES = b"\x02"
    INF_ADDR = b"\x03"

    INF_TRANSACTION = b"\x04"
    INF_BLOCK = b"\x05"

    REQ_BLOCK = b"\x06"
    REQ_BLOCKS = b"\x07"
    REQ_ADDR_LIST = b"\x08"

    # All server reply type codes...
    # ...when receive a PING:
    PONG = b"\x00"

    # ...when receive a REQ_SWAP_ROLES/INF_TRANSACTION/INF_BLOCK:
    REP_PROCEED = b"\x00"
    REP_STOP = b"\x01"

    # More field sizes:
    TOKEN_FSZ = 4
    HOSTNAME_LEN_FSZ = 1
    BLOCK_HEIGHT_FSZ = 4
    BLOCK_LIST_LEN_FSZ = 1
    ADDR_LIST_LEN_FSZ = 1

    # Deduced limits:
    MAX_HOSTNAME_LEN = 2 ** (8*HOSTNAME_LEN_FSZ) - 1
    MAX_BLOCK_HEIGHT = 2 ** (8*BLOCK_HEIGHT_FSZ) - 1
    MAX_BLOCKS = 2 ** (8*BLOCK_LIST_LEN_FSZ) - 1
    MAX_ADDRS = 2 ** (8*ADDR_LIST_LEN_FSZ) - 1
