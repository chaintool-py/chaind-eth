# standard imports
import unittest

# external imports
from chainlib.eth.gas import (
        RPCGasOracle,
        Gas,
        )
from chainlib.eth.nonce import (
        RPCNonceOracle,
        )
from chainlib.eth.tx import (
        TxFormat,
        unpack,
        )
from hexathon import (
        strip_0x,
        )

# test imports
from tests.chaind_eth_base import TestBase

class TestChain(TestBase):

    def test_chain_interface(self):
        gas_oracle = RPCGasOracle(conn=self.rpc)
        nonce_oracle = RPCNonceOracle(self.accounts[0], conn=self.rpc)
        c = Gas(self.chain_spec, signer=self.signer, gas_oracle=gas_oracle, nonce_oracle=nonce_oracle)
        (tx_hash, tx_raw_rlp_signed) = c.create(self.accounts[0], self.accounts[1], 1024, tx_format=TxFormat.RLP_SIGNED)

        tx_raw_rlp_signed_bytes = bytes.fromhex(strip_0x(tx_raw_rlp_signed))
        tx_src = unpack(tx_raw_rlp_signed_bytes, self.chain_spec)
        tx_src = self.interface.src_normalize(tx_src)
        assert tx_src['gas_price'] == tx_src['gasPrice']


if __name__ == '__main__':
    unittest.main()
