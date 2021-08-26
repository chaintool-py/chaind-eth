# standard imports
import logging
import datetime

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
from chainqueue.enum import (
        StatusBits,
        errors as queue_errors,
        )

# local imports
from chainqueue.adapters.base import Adapter

logg = logging.getLogger(__name__)


class EthAdapter(Adapter):

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


    def upcoming(self, chain_spec, session=None):
        txs = self.backend.get(chain_spec, self.translate, session=session, status=StatusBits.QUEUED, not_status=StatusBits.IN_NETWORK)
        before = datetime.datetime.utcnow() - self.error_retry_threshold
        errored_txs = self.backend.get(chain_spec, self.translate, session=session, status=StatusBits.LOCAL_ERROR, not_status=StatusBits.FINAL, before=before, requeue=True)
        for tx_hash in errored_txs.keys():
            txs[tx_hash] = errored_txs[tx_hash]
        return txs


    def add(self, bytecode, chain_spec, session=None):
        tx = self.translate(bytecode, chain_spec)
        r = self.backend.create(chain_spec, tx['nonce'], tx['from'], tx['hash'], add_0x(bytecode.hex()), session=session)
        if r:
            session.rollback()
            session.close()
            return r
        r = self.backend.cache(tx, session=session)
        session.commit()
        return r


#    def cache(self, chain_spec):
#        session = self.backend.create_session()
#        r = self.backend.create(chain_spec, tx['nonce'], tx['from'], tx['hash'], add_0x(bytecode.hex()), session=session)
#        session.close()

