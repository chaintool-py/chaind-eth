# standard imports
import sys
import time
import socket
import signal
import os
import logging
import stat
import argparse
import uuid

# external imports
import chainlib.eth.cli
from chaind import Environment
import confini
from hexathon import strip_0x
from chainlib.chain import ChainSpec
from chainlib.eth.connection import EthHTTPConnection
from chainlib.eth.block import block_latest
from chainsyncer.driver.head import HeadSyncer
from chainsyncer.driver.history import HistorySyncer
from chainsyncer.db import dsn_from_config
from chainsyncer.db.models.base import SessionBase
from chainsyncer.backend.sql import SQLBackend
from chainsyncer.error import SyncDone

# local imports
from chaind_eth.filter import StateFilter
from chaind_eth.chain import EthChainInterface

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '..', 'data', 'config')

env = Environment(domain='eth', env=os.environ)

arg_flags = chainlib.eth.cli.argflag_std_read
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)
argparser.add_argument('--data-dir', type=str, help='data directory')
argparser.add_argument('--runtime-dir', type=str, help='runtime directory')
argparser.add_argument('--session-id', dest='session_id', type=str, help='session identifier')
argparser.add_argument('--offset', default=0, type=int, help='block height to sync history from')
args = argparser.parse_args()
extra_args = {
    'runtime_dir': 'SESSION_RUNTIME_DIR',
    'data_dir': 'SESSION_DATA_DIR',
    'session_id': 'SESSION_ID', 
    'offset': 'SYNCER_HISTORY_START',
        }
#config = chainlib.eth.cli.Config.from_args(args, arg_flags, default_config_dir=config_dir, extend_base_config_dir=config_dir)
config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=[config_dir, os.path.join(config_dir, 'syncer')])

logg.debug('session id {} {}'.format(type(config.get('SESSION_ID')), config.get('SESSION_ID')))
if config.get('SESSION_ID') == None:
    config.add(env.session, 'SESSION_ID', exists_ok=True)
if config.get('SESSION_RUNTIME_DIR') == None:
    config.add(env.runtime_dir, 'SESSION_RUNTIME_DIR', exists_ok=True)
if config.get('SESSION_DATA_DIR') == None:
    config.add(env.data_dir, 'SESSION_DATA_DIR', exists_ok=True)
if not config.get('SESSION_SOCKET_PATH'):
    socket_path = os.path.join(config.get('SESSION_RUNTIME_DIR'), config.get('SESSION_ID'), 'chaind.sock')
    config.add(socket_path, 'SESSION_SOCKET_PATH', True)

if config.get('DATABASE_ENGINE') == 'sqlite':
    config.add(os.path.join(config.get('SESSION_DATA_DIR'), config.get('DATABASE_NAME')), 'DATABASE_NAME', exists_ok=True)
    
config.censor('PASSWORD', 'DATABASE')
logg.debug('config loaded:\n{}'.format(config))


chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

dsn = dsn_from_config(config)
logg.debug('dns {}'.format(dsn))
SQLBackend.setup(dsn, debug=config.true('DATABASE_DEBUG'))
rpc = EthHTTPConnection(url=config.get('RPC_HTTP_PROVIDER'), chain_spec=chain_spec)

def register_filter_tags(filters, session):
    for f in filters:
        tag = f.tag()
        try:
            add_tag(session, tag[0], domain=tag[1])
            session.commit()
            logg.info('added tag name "{}" domain "{}"'.format(tag[0], tag[1]))
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            logg.debug('already have tag name "{}" domain "{}"'.format(tag[0], tag[1]))


def main():
    o = block_latest()
    r = rpc.do(o)
    block_offset = int(strip_0x(r), 16) + 1

    syncers = []

    syncer_backends = SQLBackend.resume(chain_spec, block_offset)

    if len(syncer_backends) == 0:
        initial_block_start = config.get('SYNCER_HISTORY_START', 0)
        if isinstance(initial_block_start, str):
            initial_block_start = int(initial_block_start)
        initial_block_offset = block_offset
        if config.true('SYNCER_SKIP_HISTORY'):
            initial_block_start = block_offset
            initial_block_offset += 1
        syncer_backends.append(SQLBackend.initial(chain_spec, initial_block_offset, start_block_height=initial_block_start))
        logg.info('found no backends to resume, adding initial sync from history start {} end {}'.format(initial_block_start, initial_block_offset))
    else:
        for syncer_backend in syncer_backends:
            logg.info('resuming sync session {}'.format(syncer_backend))

    chain_interface = EthChainInterface()
    for syncer_backend in syncer_backends:
        syncers.append(HistorySyncer(syncer_backend, chain_interface))

    syncer_backend = SQLBackend.live(chain_spec, block_offset+1)
    syncers.append(HeadSyncer(syncer_backend, chain_interface))

    state_filter = StateFilter(chain_spec)
    filters = [
        state_filter,
            ]

    i = 0
    for syncer in syncers:
        logg.debug('running syncer index {}'.format(i))
        for f in filters:
            syncer.add_filter(f)
        r = syncer.loop(int(config.get('SYNCER_LOOP_INTERVAL')), rpc)
        sys.stderr.write("sync {} done at block {}\n".format(syncer, r))

        i += 1

    sys.exit(0)


if __name__ == '__main__':
    main()
