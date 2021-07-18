# standard imports
import unittest
import logging
import os

# external imports
from potaahto.symbols import snake_and_camel
from hexathon import (
        strip_0x,
        )
from chainqueue.adapters.eth import EthAdapter
from chainqueue.unittest.db import (
        db_config,
        dsn_from_config,
        )
from chainqueue.sql.backend import SQLBackend
from chainqueue.enum import is_alive
from chainqueue.sql.query import get_tx
from chainlib.eth.gas import (
        RPCGasOracle,
        Gas,
        )
from chainlib.eth.nonce import (
        RPCNonceOracle,
        )
from chainlib.eth.tx import (
        TxFormat,
        raw,
        unpack,
        receipt,
        Tx,
        )
from chainlib.eth.block import (
        block_by_hash,
        Block,
        )
from chainqueue.sql.state import (
        set_sent,
        set_reserved,
        set_ready,
        )

# local imports
from chaind_eth.filter import StateFilter
from chaind_eth.chain import EthChainInterface

# test imports
from tests.chaind_eth_base import TestBase

logging.basicConfig(level=logging.DEBUG)
logg = logging.getLogger()


class TestFilter(TestBase):

    def test_filter(self):
        gas_oracle = RPCGasOracle(conn=self.rpc)
        nonce_oracle = RPCNonceOracle(self.accounts[0], conn=self.rpc)
        c = Gas(self.chain_spec, signer=self.signer, gas_oracle=gas_oracle, nonce_oracle=nonce_oracle)
        (tx_hash, tx_raw_rlp_signed) = c.create(self.accounts[0], self.accounts[1], 1024, tx_format=TxFormat.RLP_SIGNED)
        o = raw(tx_raw_rlp_signed)
        self.rpc.do(o)

        #o = receipt(tx_hash)
        o = self.interface.tx_receipt(tx_hash)
        rcpt = self.rpc.do(o)

        #o = block_by_hash(rcpt['block_hash'])
        o = self.interface.block_by_number(rcpt['block_number'])
        block_src = self.rpc.do(o)
        #block = Block(block_src)
        block = self.interface.block_from_src(block_src)

        dsn = dsn_from_config(db_config)
        backend = SQLBackend(dsn, debug=bool(os.environ.get('DATABASE_DEBUG')))
        adapter = EthAdapter(backend)

        tx_raw_rlp_signed_bytes = bytes.fromhex(strip_0x(tx_raw_rlp_signed))
        adapter.add(tx_raw_rlp_signed_bytes, self.chain_spec, session=self.session_chainqueue)
 
        set_ready(self.chain_spec, tx_hash, session=self.session_chainqueue)
        set_reserved(self.chain_spec, tx_hash, session=self.session_chainqueue)
        set_sent(self.chain_spec, tx_hash, session=self.session_chainqueue)      

        tx_src = unpack(tx_raw_rlp_signed_bytes, self.chain_spec)
        tx_src = self.interface.src_normalize(tx_src)
        tx = Tx(tx_src, block=block, rcpt=rcpt)

        tx_repr = get_tx(self.chain_spec, tx_hash, session=self.session_chainqueue)
        assert is_alive(tx_repr['status']) 

        fltr = StateFilter(self.chain_spec)
        fltr.filter(self.rpc, block, tx, session=self.session_chainqueue)

        tx_repr = get_tx(self.chain_spec, tx_hash, session=self.session_chainqueue)
        assert not is_alive(tx_repr['status']) 


if __name__ == '__main__':
    unittest.main()
