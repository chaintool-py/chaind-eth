# stanndard imports
import logging
import unittest

# external imports
from chainlib.eth.tx import unpack
from chainqueue.sql.query import get_tx
from chainqueue.enum import StatusBits

# local imports
from chaind_eth.dispatch import Dispatcher

# test imports
from tests.chaind_eth_base import TestSQLBase

logging.basicConfig(level=logging.DEBUG)



class TestDispatcher(TestSQLBase):

    def test_dispatch_process(self):
        dispatcher = Dispatcher(self.chain_spec, self.adapter, 1)
        self.adapter.add(self.example_tx, self.chain_spec, session=self.session_chainqueue)
        assert dispatcher.get_count(self.example_tx_sender, self.session_chainqueue) == 1
        dispatcher.process(self.rpc, self.session_chainqueue)
        tx_obj = unpack(self.example_tx, self.chain_spec)
        o = get_tx(self.chain_spec, tx_obj['hash'], session=self.session_chainqueue)
        assert o['status'] & StatusBits.IN_NETWORK > 0
        
        assert dispatcher.get_count(self.example_tx_sender, self.session_chainqueue) == 0

if __name__ == '__main__':
    unittest.main()
