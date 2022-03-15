# standard imports
import os
import tempfile
import unittest
import shutil
import logging
import hashlib

# external imports
from chainlib.chain import ChainSpec
from chainqueue.cache import CacheTokenTx
from chainlib.error import RPCException
from chainlib.status import Status as TxStatus
from chaind.unittest.common import TestChaindFsBase
from chaind.driver import QueueDriver
from chaind.filter import StateFilter
from chainlib.eth.gas import Gas

# local imports
from chaind.eth.cache import EthCacheTx

logging.basicConfig(level=logging.DEBUG)
logg = logging.getLogger()


class TestEthChaindFs(TestChaindFsBase):

    def setUp(self):
        self.cache_adapter = EthCacheTx
        super(TestEthChaindFs, self).setUp()


    def test_deserialize(self):
        data = "f8610d2a82520894eb3907ecad74a0013c259d5874ae7f22dcbcc95c8204008078a0ddbebd76701f6531e5ea42599f890268716e2bb38e3e125874f47595c2338049a00f5648d17b20efac8cb7ff275a510ebef6815e1599e29067821372b83eb1d28c"
        hsh = self.adapter.put(data)
        v = self.adapter.get(hsh)
        self.assertEqual(data, v)


if __name__ == '__main__':
    unittest.main()
