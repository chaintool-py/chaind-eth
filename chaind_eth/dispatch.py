# standard imports
import logging

# external imports
from chainlib.eth.address import to_checksum_address
from chainlib.eth.tx import unpack
from chainlib.error import JSONRPCException
from chainqueue.enum import StatusBits
from chainqueue.sql.query import count_tx
from hexathon import strip_0x

#logg = logging.getLogger(__name__)
logg = logging.getLogger()


class Dispatcher:

    status_inflight_mask = StatusBits.IN_NETWORK | StatusBits.FINAL
    status_inflight_mask_match = StatusBits.IN_NETWORK

    def __init__(self, chain_spec, adapter, limit=100):
        self.address_counts = {}
        self.chain_spec = chain_spec
        self.adapter = adapter
        self.limit = limit


    def __init_count(self, address, session):
        c = self.address_counts.get(address)
        if c == None:
            c = self.limit - count_tx(self.chain_spec, address, self.status_inflight_mask, self.status_inflight_mask_match, session=session)
            if c < 0:
                c = 0
            self.address_counts[address] = c
        return c


    def get_count(self, address, session):
        return self.__init_count(address, session)

    
    def inc_count(self, address, session):
        self.__init_count(address, session)
        self.address_counts[address] -= 1
            
    
    def process(self, rpc, session):
        c = 0
        txs = self.adapter.upcoming(self.chain_spec, session=session)
        for k in txs.keys():
            signed_tx_bytes = bytes.fromhex(strip_0x(txs[k]))
            tx_obj = unpack(signed_tx_bytes, self.chain_spec)
            sender = to_checksum_address(tx_obj['from'])
            address_count = self.get_count(sender, session)
            if address_count == 0:
                logg.debug('too many inflight txs for {}, skipping {}'.format(sender, k))
                continue
            logg.debug('processing tx {} {}'.format(k, txs[k]))
            r = 0
            try:
                r = self.adapter.dispatch(self.chain_spec, rpc, k, txs[k], session)
            except JSONRPCException as e:
                logg.error('dispatch failed for {}: {}'.format(k, e))
                continue
            if r == 0:
                self.inc_count(sender, session)
                c += 1
        return c
