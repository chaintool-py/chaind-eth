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
from chaind.unittest.fs import TestChaindFsBase
from chaind.driver import QueueDriver
from chaind.filter import StateFilter
from chainlib.eth.gas import Gas
from jsonrpc_std.parse import jsonrpc_validate_dict
from hexathon import strip_0x

# local imports
from chaind.eth.cache import EthCacheTx
from chaind.eth.dispatch import EthDispatcher

logging.basicConfig(level=logging.DEBUG)
logg = logging.getLogger()


class MockConn:

    def __init__(self):
        self.fails = []
        self.last = None


    def add_fail(self, v):
        self.fails.append(v)


    def do(self, v):
        if v in self.fails:
            raise RuntimeError(v)
        v = jsonrpc_validate_dict(v)
        if v['method'] != 'eth_sendRawTransaction':
            raise ValueError('unsupported method {}'.format(v['method']))
        self.last = v['params'][0]


class TestEthChaindFs(TestChaindFsBase):

    def setUp(self):
        self.cache_adapter = EthCacheTx
        self.conn = MockConn()
        self.dispatcher = EthDispatcher(self.conn)
        super(TestEthChaindFs, self).setUp()


    def test_deserialize(self):
        data = "f8610d2a82520894eb3907ecad74a0013c259d5874ae7f22dcbcc95c8204008078a0ddbebd76701f6531e5ea42599f890268716e2bb38e3e125874f47595c2338049a00f5648d17b20efac8cb7ff275a510ebef6815e1599e29067821372b83eb1d28c" # valid RLP example data
        hsh = self.adapter.put(data)
        v = self.adapter.get(hsh)
        self.assertEqual(data, v)


    def test_dispatch(self):
        data = "f8610d2a82520894eb3907ecad74a0013c259d5874ae7f22dcbcc95c8204008078a0ddbebd76701f6531e5ea42599f890268716e2bb38e3e125874f47595c2338049a00f5648d17b20efac8cb7ff275a510ebef6815e1599e29067821372b83eb1d28c" # valid RLP example data
        hsh = self.adapter.put(data)
        self.adapter.dispatch(hsh)
        self.assertEqual(strip_0x(self.conn.last), strip_0x(data))


if __name__ == '__main__':
    unittest.main()
