# SPDX-License-Identifier: GPL-3.0-or-later

# standard imports
import os
import logging
import sys
import datetime

# external imports
from hexathon import (
        add_0x,
        strip_0x,
        )
from chaind import Environment
import chainlib.eth.cli
from chainlib.chain import ChainSpec
from chainqueue.db import dsn_from_config
from chainqueue.sql.backend import SQLBackend
from chainqueue.enum import StatusBits
from chaind.sql.session import SessionIndex
from chainqueue.adapters.eth import EthAdapter
from chainlib.eth.gas import price
from chainlib.eth.connection import EthHTTPConnection
from crypto_dev_signer.eth.transaction import EIP155Transaction

DEFAULT_GAS_FACTOR = 1.1


logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__)) 
config_dir = os.path.join(script_dir, '..', 'data', 'config')

arg_flags = chainlib.eth.cli.argflag_std_write
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)
argparser.add_argument('--backend', type=str, default='sql', help='Backend to use (currently only "sql")')
argparser.add_positional('session_id', required=False, type=str, help='Session id to connect to')
args = argparser.parse_args()
extra_args = {
    'backend': None,
    'session_id': 'SESSION_ID',
        }

env = Environment(domain='eth', env=os.environ)

config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=config_dir)

if config.get('SESSION_DATA_DIR') == None:
    config.add(env.data_dir, 'SESSION_DATA_DIR', exists_ok=True)

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

tx_getter = None
session_method = None
if config.get('_BACKEND') == 'sql':
    from chainqueue.sql.query import get_tx_cache as tx_getter
    from chainqueue.runnable.sql import setup_backend
    from chainqueue.db.models.base import SessionBase
    setup_backend(config, debug=config.true('DATABASE_DEBUG'))
    session_method = SessionBase.create_session
else:
    raise NotImplementedError('backend {} not implemented'.format(config.get('_BACKEND')))

if config.get('DATABASE_ENGINE') == 'sqlite':
    config.add(os.path.join(config.get('SESSION_DATA_DIR'), config.get('DATABASE_NAME') + '.sqlite'), 'DATABASE_NAME', exists_ok=True)
 
wallet = chainlib.eth.cli.Wallet()
wallet.from_config(config)

rpc = chainlib.eth.cli.Rpc(wallet=wallet)
conn = rpc.connect_by_config(config)

dsn = dsn_from_config(config)
backend = SQLBackend(dsn, debug=config.true('DATABASE_DEBUG'), error_parser=rpc.error_parser)
session_index_backend = SessionIndex(config.get('SESSION_ID'))
adapter = EthAdapter(backend, session_index_backend=session_index_backend)


def main():
    before = datetime.datetime.utcnow() - adapter.pending_retry_threshold
    txs = session_index_backend.get(chain_spec, adapter, status=StatusBits.IN_NETWORK, not_status=StatusBits.FINAL | StatusBits.OBSOLETE, before=before)

    o = price()
    r = conn.do(o, error_parser=rpc.error_parser)
    gas_price = strip_0x(r)
    try:
        gas_price = int(gas_price, 16)
    except ValueError:
        gas_price = int(gas_price)
    logg.info('got current gas price {}'.format(gas_price))

    signer = rpc.get_signer()

    db_session = adapter.create_session()
    for tx_hash in txs:
        tx_bytes = bytes.fromhex(strip_0x(txs[tx_hash]))
        tx = adapter.translate(tx_bytes, chain_spec)
        tx_gas_price = int(tx['gasPrice'])
        if tx_gas_price < gas_price:
            tx['gasPrice'] = gas_price
        else:
            tx['gasPrice'] = int(tx['gasPrice'] * DEFAULT_GAS_FACTOR)
        tx_obj = EIP155Transaction(tx, tx['nonce'], chain_spec.chain_id())
        new_tx_bytes = signer.sign_transaction_to_wire(tx_obj)
        logg.debug('add tx {} with gas price changed from {} to {}: {}'.format(tx_hash, tx_gas_price, tx['gasPrice'], new_tx_bytes.hex()))
        adapter.add(new_tx_bytes, chain_spec, session=db_session)

    db_session.close()


if __name__ == '__main__':
    main()
