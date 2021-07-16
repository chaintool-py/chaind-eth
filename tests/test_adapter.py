# stanndard imports
import logging
import unittest
import os

# external imports
from chainqueue.sql.backend import SQLBackend
from chainlib.chain import ChainSpec
from chainqueue.unittest.db import (
        db_config,
        dsn_from_config,
        )

# local imports
from chainqueue.adapters.eth import EthAdapter

# test imports
from tests.chaind_eth_base import TestBase

logging.basicConfig(level=logging.DEBUG)


class TestAdapter(TestBase):

    example_tx = bytes.fromhex('f8640183989680825208948311ad69b3429400ab795d45af85d204f73329ae8204d38026a097a7fd66548e4c116270b547ac7ed8cb531b0b97f80d49b45986144e47dbe44da07cc4345741dc0fabf65a473c0d3a1536cd501961f7e01b07dd8e107ff87d1556')
    dsn = dsn_from_config(db_config)

    def setUp(self):
        super(TestAdapter, self).setUp()
        self.chain_spec = ChainSpec.from_chain_str('foo:bar:1:baz')
        self.backend = SQLBackend(self.dsn, debug=bool(os.environ.get('DATABASE_DEBUG')))
        self.adapter = EthAdapter(self.backend)


    def test_eth_adapter_translate(self):
        self.adapter.translate(self.chain_spec, self.example_tx)
        # succesful decode means translate is working, no further checks needed


    def test_eth_adapter_add(self):
        self.adapter.add(self.chain_spec, self.example_tx, session=self.session_chainqueue)
            

if __name__ == '__main__':
    unittest.main()
