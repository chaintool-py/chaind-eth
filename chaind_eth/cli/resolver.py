# standard imports
import logging

# external imports
from chainlib.eth.constant import ZERO_ADDRESS
from chainlib.eth.address import is_checksum_address
from hexathon import strip_0x
from eth_token_index.index import TokenUniqueSymbolIndex

logg = logging.getLogger(__name__)


class LookNoop:

    def __init__(self, check=True):
        self.check = check


    def get(self, k, rpc=None):
        if not self.check:
            address_bytes = bytes.fromhex(strip_0x(k))
            if len(address_bytes) != 20:
                raise ValueError('{} is not a valid address'.format(k))
        else:
            try:
                if not is_checksum_address(k):
                    raise ValueError('not valid checksum address {}'.format(k))
            except ValueError:
                raise ValueError('not valid checksum address {}'.format(k))
        return strip_0x(k)


    def __str__(self):
        return 'checksum address shortcircuit'


class TokenIndexLookup(TokenUniqueSymbolIndex):


    def __init__(self, chain_spec, signer, gas_oracle, nonce_oracle, address, sender_address=ZERO_ADDRESS):
        super(TokenIndexLookup, self).__init__(chain_spec, signer=signer, gas_oracle=gas_oracle, nonce_oracle=nonce_oracle)
        self.local_address = address
        self.sender_address = sender_address


    def get(self, k, rpc=None):
        o = self.address_of(self.local_address, k, sender_address=self.sender_address)
        r = rpc.do(o)
        address = self.parse_address_of(r)
        if address != ZERO_ADDRESS:
            return address
        raise FileNotFoundError(address)


    def __str__(self):
        return 'token symbol index'


class DefaultResolver:

    def __init__(self, chain_spec, rpc, sender_address=ZERO_ADDRESS):
        self.chain_spec = chain_spec
        self.rpc = rpc
        self.lookups = []
        self.lookup_pointers = []
        self.cursor = 0
        self.sender_address = sender_address


    def add_lookup(self, lookup, reverse):
        self.lookups.append(lookup)
        self.lookup_pointers.append(reverse)


    def lookup(self, k):
        if k == '' or k == None:
            return None
        for lookup in self.lookups:
            try:
                address = lookup.get(k, rpc=self.rpc)
                logg.debug('resolved token {} to {} with lookup {}'.format(k, address, lookup))
                return address
            except Exception as e:
                logg.debug('lookup {} failed for {}: {}'.format(lookup, k, e))

        raise FileNotFoundError(k)
