# standard imports
import logging

# external imports
from chainlib.eth.constant import ZERO_ADDRESS
from chainlib.eth.tx import (
        unpack,
        raw,
        )
from hexathon import (
        add_0x,
        strip_0x,
        )

# local imports
from chainqueue.adapters.sessionindex import SessionIndexAdapter

logg = logging.getLogger(__name__)


class EthAdapter(SessionIndexAdapter):


    def translate(self, bytecode, chain_spec):
        logg.debug('bytecode {}'.format(bytecode))
        tx = unpack(bytecode, chain_spec)
        tx['source_token'] = ZERO_ADDRESS
        tx['destination_token'] = ZERO_ADDRESS
        tx['from_value'] = tx['value']
        tx['to_value'] = tx['value']
        return tx


    def dispatch(self, chain_spec, rpc, tx_hash, signed_tx, session=None):
        o = raw(signed_tx)
        r = self.backend.dispatch(chain_spec, rpc, tx_hash, o)
        return r


#    def cache(self, chain_spec):
#        session = self.backend.create_session()
#        r = self.backend.create(chain_spec, tx['nonce'], tx['from'], tx['hash'], add_0x(bytecode.hex()), session=session)
#        session.close()

