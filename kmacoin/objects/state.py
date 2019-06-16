from kmacoin.globaldef.signature import verify, bytes_to_public_key
from kmacoin.objects.transaction import Transaction
from kmacoin.objects.coin import Coin

from typing import Dict, Tuple


class TransactionError(Exception):
    """
    Raised when an invalid transaction is processed.

    Attributes:
        code: a type code indicates why the transaction is invalid.
        tx: the invalid transaction.

    """

    # All error codes:
    DUP_COIN = 0
    COIN_NOT_FOUND = 1
    INVALID_SIG = 2
    UNBALANCE = 3

    def __init__(self, msg: str, code: int, tx: Transaction):
        super().__init__(msg)
        self.code = code
        self.tx = tx


class State(object):
    """
    This class represents a state in KMA-Coin system.

    Attributes:
        coins: a dictionary of the form: (tx_id, seq) -> coin, represents all
            coins in the state.

    """
    coins: Dict[Tuple[bytes, int], Coin]

    def __init__(self):
        self.coins = {}

    def process_transaction(self, tx: Transaction,
                            check_balance: bool = True) -> int:
        """
        Process a transaction and let this state transit.

        Args:
            tx: the transaction to be processed.
            check_balance: if True, reject when the transaction is unbalanced.

        Raises:
            (TransactionError): in case the transaction is invalid.

        Returns:
            the transaction fee.

        """
        # check for non-existent input coins
        try:
            input_coins = [self.coins[coin_id] for coin_id in tx.input_ids]
        except KeyError:
            raise TransactionError(
                "Input coin not found!",
                TransactionError.COIN_NOT_FOUND,
                tx
            )

        # check for duplicate input coins
        if len(set(input_coins)) < len(input_coins):
            raise TransactionError(
                "Duplicate input coin found!",
                TransactionError.DUP_COIN,
                tx
            )

        # check for incorrect signatures
        owners = set(coin.owner for coin in input_coins)
        sigs = set(tx.sigs)
        signed_data = tx.get_signed_data()
        for owner in owners:
            pubkey = bytes_to_public_key(owner)

            # try to find a valid signature
            correct = False
            for sig in sigs:
                if verify(pubkey, sig, signed_data):
                    correct = True
                    sigs.remove(sig)
                    break

            if not correct:
                raise TransactionError(
                    "Invalid signature!",
                    TransactionError.INVALID_SIG,
                    tx
                )

        # get the fee
        total_in_val = sum(coin.value for coin in input_coins)
        total_out_val = sum(coin.value for coin in tx.outputs)
        fee = total_in_val - total_out_val

        # check balance
        if check_balance and fee < 0:
            raise TransactionError(
                "Transaction is unbalanced!",
                TransactionError.UNBALANCE,
                tx
            )

        # destroy input coins
        for coin_id in tx.input_ids:
            del self.coins[coin_id]

        # create output coins
        for i in range(len(tx.outputs)):
            self.coins[(tx.get_id(), i)] = tx.outputs[i]

        # return the transaction fee
        return fee
