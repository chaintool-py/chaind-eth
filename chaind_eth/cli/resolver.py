# standard imports
import logging

# external imports
from chainlib.eth.constant import ZERO_ADDRESS

logg = logging.getLogger(__name__)


class DefaultResolver:

    def __init__(self, chain_spec, rpc, sender_address=ZERO_ADDRESS):
        self.chain_spec = chain_spec
        self.rpc = rpc
        self.lookups = []
        self.lookup_pointers = []
        self.cursor = 0
        self.sender_address = sender_address


    def add_lookup(self, lookup, address):
        self.lookups.append(lookup)
        self.lookup_pointers.append(address)


    def lookup(self, k):
        for i, lookup in enumerate(self.lookups):
            address = self.lookup_pointers[i]
            o = lookup.address_of(address, k, sender_address=self.sender_address)
            r = self.rpc.do(o)
            address = lookup.parse_address_of(r)
            if address == ZERO_ADDRESS:
                address = None
            return address

        raise FileNotFoundError(k)
