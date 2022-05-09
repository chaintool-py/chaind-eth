# external imports
from hexathon import strip_0x
from chainqueue.cache import (
        CacheTx,
        NoopNormalizer,
        )
from chainlib.eth.tx import unpack
from chainlib.encode import TxHexNormalizer


class Normalizer(TxHexNormalizer, NoopNormalizer):

    def __init__(self):
        super(Normalizer, self).__init__()
        self.address = self.wallet_address
        self.hash = self.tx_hash
        #self.value = self.noop


    def value(self, v):
        hexathon.to_int(v)


eth_normalizer = Normalizer()


class EthCacheTx(CacheTx):

    def __init__(self, chain_spec):
        super(EthCacheTx, self).__init__(chain_spec)


    def deserialize(self, signed_tx):
        signed_tx_bytes = bytes.fromhex(strip_0x(signed_tx))
        tx = unpack(signed_tx_bytes, self.chain_spec)
        self.hash = eth_normalizer.hash(tx['hash'])
        self.sender = eth_normalizer.address(tx['from'])
        self.recipient = eth_normalizer.address(tx['to'])
        self.nonce = eth_normalizer.value(tx['nonce'])
        self.value = eth_normalizer.value(tx['value'])
        self.src = signed_tx
