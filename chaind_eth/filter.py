# standard imports
import logging

# external imports
from chainlib.status import Status
from chainqueue.sql.query import get_tx
from chainqueue.error import NotLocalTxError
from chainqueue.sql.state import set_final

logg = logging.getLogger(__name__)


class StateFilter:

    def __init__(self, chain_spec):
        self.chain_spec = chain_spec


    def filter(self, conn, block, tx, session=None):
        otx = None
        try:
            otx = get_tx(self.chain_spec, tx.hash, session=session)
        except NotLocalTxError:
            return False
        logg.info('finalizing local tx {} with status {}'.format(tx.hash, tx.status))
        status = tx.status != Status.SUCCESS
        set_final(self.chain_spec, tx.hash, block=block.number, tx_index=tx.index, fail=status, session=session)
