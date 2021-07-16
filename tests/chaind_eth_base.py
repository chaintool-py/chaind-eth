# standard imports
import unittest

# external imports
from chainsyncer.unittest.db import ChainSyncerDb
from chainqueue.unittest.db import ChainQueueDb
from chainlib.eth.unittest.ethtester import EthTesterCase


class TestBase(EthTesterCase):

    def setUp(self):
        super(TestBase, self).setUp()
        self.db_chainsyncer = ChainSyncerDb()
        self.session_chainsyncer = self.db_chainsyncer.bind_session()

        self.db_chainqueue = ChainQueueDb()
        self.session_chainqueue = self.db_chainqueue.bind_session()

    def tearDown(self):
        self.session_chainsyncer.commit()
        self.db_chainsyncer.release_session(self.session_chainsyncer)
        self.session_chainqueue.commit()
        self.db_chainqueue.release_session(self.session_chainqueue)
        super(TestBase, self).tearDown()
