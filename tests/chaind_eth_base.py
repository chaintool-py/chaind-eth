# standard imports
import os
import unittest

# external imports
from chainsyncer.unittest.db import ChainSyncerDb
from chainqueue.unittest.db import ChainQueueDb
from chainlib.eth.unittest.ethtester import EthTesterCase
from chainqueue.adapters.eth import EthAdapter
from chainqueue.unittest.db import (
        db_config,
        dsn_from_config,
        )
from chainqueue.sql.backend import SQLBackend
from chainlib.eth.address import to_checksum_address
from hexathon import add_0x

# local imports
from chaind_eth.chain import EthChainInterface

class TestBase(EthTesterCase):

    def setUp(self):
        super(TestBase, self).setUp()
        self.db_chainsyncer = ChainSyncerDb()
        self.session_chainsyncer = self.db_chainsyncer.bind_session()

        self.db_chainqueue = ChainQueueDb()
        self.session_chainqueue = self.db_chainqueue.bind_session()

        self.interface = EthChainInterface()

    def tearDown(self):
        self.session_chainsyncer.commit()
        self.db_chainsyncer.release_session(self.session_chainsyncer)
        self.session_chainqueue.commit()
        self.db_chainqueue.release_session(self.session_chainqueue)
        super(TestBase, self).tearDown()


class TestSQLBase(TestBase):

    example_tx = bytes.fromhex('f8650d8405f5e10082520894ee38d3a40e177608d41978778206831f60dd0fa88204008077a040adee2ad0a0e566bced4b76a8899549e86719eb8866b87674b6fdc88479c201a030b3ca061bb330f4d78bc9cb8144c8e570339496f56b7809387de2ffeaa585d5')
    example_tx_sender = add_0x(to_checksum_address('eb3907ecad74a0013c259d5874ae7f22dcbcc95c'))
    dsn = dsn_from_config(db_config)

    def setUp(self):
        super(TestSQLBase, self).setUp()
        self.backend = SQLBackend(self.dsn, debug=bool(os.environ.get('DATABASE_DEBUG')))
        self.adapter = EthAdapter(self.backend)
