# stanndard imports
import logging
import unittest

# external imports
from chainlib.chain import ChainSpec

# test imports
from tests.chaind_eth_base import TestSQLBase

logging.basicConfig(level=logging.DEBUG)


class TestAdapter(TestSQLBase):

    def test_eth_adapter_translate(self):
        self.adapter.translate(self.example_tx, self.chain_spec)
        # succesful decode means translate is working, no further checks needed


    def test_eth_adapter_add(self):
        self.adapter.add(self.example_tx_hex, self.chain_spec, session=self.session_chainqueue)
            

if __name__ == '__main__':
    unittest.main()
