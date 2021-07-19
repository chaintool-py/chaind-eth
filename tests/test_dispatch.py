# stanndard imports
import logging
import unittest

# external imports
from hexathon import strip_0x
from chainlib.eth.tx import (
        unpack,
        TxFormat,
        )
from chainqueue.sql.query import get_tx
from chainqueue.enum import StatusBits
from chainlib.eth.gas import (
        RPCGasOracle,
        Gas,
        )
from chainlib.eth.nonce import (
        RPCNonceOracle,
        )

# local imports
from chaind_eth.dispatch import Dispatcher

# test imports
from tests.chaind_eth_base import TestSQLBase

logging.basicConfig(level=logging.DEBUG)


class TestDispatcher(TestSQLBase):

    def test_dispatch_process(self):
        gas_oracle = RPCGasOracle(conn=self.rpc)
        nonce_oracle = RPCNonceOracle(self.accounts[0], conn=self.rpc)
        c = Gas(self.chain_spec, signer=self.signer, gas_oracle=gas_oracle, nonce_oracle=nonce_oracle)
        (tx_hash, tx_raw_rlp_signed) = c.create(self.accounts[0], self.accounts[1], 1024, tx_format=TxFormat.RLP_SIGNED)

        tx_raw_rlp_signed_bytes = bytes.fromhex(strip_0x(tx_raw_rlp_signed))
        dispatcher = Dispatcher(self.chain_spec, self.adapter, 1)
        self.adapter.add(tx_raw_rlp_signed_bytes, self.chain_spec, session=self.session_chainqueue)
        assert dispatcher.get_count(self.example_tx_sender, self.session_chainqueue) == 1
        dispatcher.process(self.rpc, self.session_chainqueue)
        tx_obj = unpack(tx_raw_rlp_signed_bytes, self.chain_spec)
        o = get_tx(self.chain_spec, tx_obj['hash'], session=self.session_chainqueue)
        assert o['status'] & StatusBits.IN_NETWORK > 0
        
        assert dispatcher.get_count(self.accounts[0], self.session_chainqueue) == 0


if __name__ == '__main__':
    unittest.main()
