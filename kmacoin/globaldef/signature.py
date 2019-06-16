"""
This module implements the digital signature scheme used by KMA-Coin.

By default, ECDSA with P-192 is used.

Functions need to be defined:
    generate_key() -> a tuple of private/public key objects
    sign(private_key: object, data: bytes) -> bytes
    verify(public_key: object, sig: bytes, signed_data: bytes) -> bool
    private_key_to_bytes(private_key: object) -> bytes
    public_key_to_bytes(public_key: object) -> bytes
    bytes_to_private_key(private_key_b: bytes) -> object
    bytes_to_public_key(public_key_b: bytes) -> object

"""
import ecdsa


def generate_key() -> tuple:
    """
    Create a pair of private/public keys.

    Returns:
        (private_key, public_key)

    """
    private_key = ecdsa.SigningKey.generate()
    return private_key, private_key.get_verifying_key()


def sign(private_key: object, data: bytes) -> bytes:
    """
    Sign a piece of data, given a private key.

    Args:
        private_key: the private key object.
        data: the data to be signed.

    Returns:
        the signature.

    """
    return private_key.sign(data)


def verify(public_key: object, sig: bytes, signed_data: bytes) -> bool:
    """
    Verify a signature, given the signed data and a public key.

    Args:
        public_key: the public key.
        sig: the signature.
        signed_data: the data was signed.

    Returns:
        True if the signature is successfully verified, otherwise False.

    """
    try:
        public_key.verify(sig, signed_data)
        return True
    except (ecdsa.keys.BadSignatureError, AssertionError):
        return False


def private_key_to_bytes(private_key: object) -> bytes:
    """Serialize a private key."""
    return private_key.to_string()


def public_key_to_bytes(public_key: object) -> bytes:
    """Serialize a public key."""
    return public_key.to_string()


def bytes_to_private_key(private_key_b: bytes) -> object:
    """Load a private key from its serialized data."""
    return ecdsa.SigningKey.from_string(private_key_b)


def bytes_to_public_key(public_key_b: bytes) -> object:
    """Load a public key from its serialized data."""
    return ecdsa.VerifyingKey.from_string(public_key_b)


# The constants below are automatically generated.
__private_key, __public_key = generate_key()
PRIVATE_KEY_SIZE = len(private_key_to_bytes(__private_key))
PUBLIC_KEY_SIZE = len(public_key_to_bytes(__public_key))
SIGNATURE_SIZE = len(sign(__private_key, b""))
