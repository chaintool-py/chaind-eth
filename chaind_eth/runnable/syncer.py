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

env = Environment(domain='eth', env=os.environ)

argparser = argparse.ArgumentParser('chainqueue transaction submission and trigger server')
argparser.add_argument('-c', '--config', dest='c', type=str, default=env.config_dir, help='configuration directory')
argparser.add_argument('-p', type=str, help='rpc endpoint')
argparser.add_argument('-i', type=str, help='chain spec')
argparser.add_argument('--runtime-dir', dest='runtime_dir', type=str, default=env.runtime_dir, help='runtime directory')
argparser.add_argument('--data-dir', dest='data_dir', type=str, default=env.data_dir, help='data directory')
argparser.add_argument('--session-id', dest='session_id', type=str, default=env.session, help='session id to use for session')
argparser.add_argument('--offset', type=int, default=0, help='block number to start sync')
argparser.add_argument('--skip-history', action='store_true', help='do not sync initial history')
argparser.add_argument('--interval', type=int, default=5, help='sync pool interval, in seconds')
argparser.add_argument('-v', action='store_true', help='be verbose')
argparser.add_argument('-vv', action='store_true', help='be very verbose')
args = argparser.parse_args(sys.argv[1:])

if args.vv:
    logg.setLevel(logging.DEBUG)
elif args.v:
    logg.setLevel(logging.INFO)

# process config
config = confini.Config(args.c)
config.process()
args_override = {
            'SESSION_RUNTIME_DIR': getattr(args, 'runtime_dir'),
            'SESSION_CHAIN_SPEC': getattr(args, 'i'),
            'RPC_ENDPOINT': getattr(args, 'p'),
            'SESSION_DATA_DIR': getattr(args, 'data_dir'),
            'SYNCER_LOOP_INTERVAL': getattr(args, 'interval'),
            'SYNCER_HISTORY_START': getattr(args, 'offset'),
            'SYNCER_SKIP_HISTORY': getattr(args, 'skip_history'),
            'SESSION_ID': getattr(args, 'session_id'),
        }
config.dict_override(args_override, 'cli flag')

if config.get('DATABASE_ENGINE') == 'sqlite':
    config.add(os.path.join(config.get('SESSION_DATA_DIR'), config.get('DATABASE_NAME')), 'DATABASE_NAME', True)
 
config.censor('PASSWORD', 'DATABASE')
logg.debug('config loaded\n{}'.format(config))

chain_spec = ChainSpec.from_chain_str(config.get('SESSION_CHAIN_SPEC'))

dsn = dsn_from_config(config)
SQLBackend.setup(dsn, debug=config.true('DATABASE_DEBUG'))
rpc = EthHTTPConnection(url=config.get('RPC_ENDPOINT'), chain_spec=chain_spec)


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
        initial_block_start = config.get('SYNCER_HISTORY_START')
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
