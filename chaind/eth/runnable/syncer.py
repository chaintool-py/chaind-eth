# standard imports
import os
import logging

# external imports
import chainlib.eth.cli
from chaind.setup import Environment
from chaind.filter import StateFilter
from chaind.adapters.fs import ChaindFsAdapter
from chainlib.eth.block import block_latest
from chainlib.eth.connection import EthHTTPConnection
from chainlib.chain import ChainSpec
from hexathon import strip_0x
from chainsyncer.store.fs import SyncFsStore
from chainsyncer.driver.chain_interface import ChainInterfaceDriver

# local imports
from chaind.eth.cache import EthCacheTx
from chaind.eth.chain import EthChainInterface

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
argparser.add_argument('--dispatch-delay', dest='dispatch_delay', type=float, help='socket timeout before processing queue')
argparser.add_argument('--offset', type=int, default=0, help='Start sync on this block')
argparser.add_argument('--until', type=int, default=0, help='Terminate sync on this block')
argparser.add_argument('--head', action='store_true', help='Start at current block height (overrides --offset, assumes --keep-alive)')
argparser.add_argument('--keep-alive', action='store_true', dest='keep_alive', help='Continue to sync head after history sync complete')
args = argparser.parse_args()
extra_args = {
    'runtime_dir': 'SESSION_RUNTIME_DIR',
    'data_dir': 'SESSION_DATA_DIR',
    'session_id': 'SESSION_ID', 
    'dispatch_delay': 'SESSION_DISPATCH_DELAY',
        }
config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=config_dir)

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
config.add(args.keep_alive, '_KEEP_ALIVE', True)
config.add(args.head, '_HEAD', True)
config.add(args.offset, '_SYNC_OFFSET', True)

logg.debug('config loaded:\n{}'.format(config))

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

conn = EthHTTPConnection(url=config.get('RPC_PROVIDER'), chain_spec=chain_spec)


def main():
    o = block_latest()
    r = conn.do(o)
    block_offset = int(strip_0x(r), 16) + 1
    logg.info('network block height is {}'.format(block_offset))

    keep_alive = False
    session_block_offset = 0
    block_limit = 0
    if args.head:
        session_block_offset = block_offset
        block_limit = -1
        keep_alive = True
    else:
        session_block_offset = args.offset

    if args.until > 0:
        if not args.head and args.until <= session_block_offset:
            raise ValueError('sync termination block number must be later than offset ({} >= {})'.format(session_block_offset, args.until))
        block_limit = args.until
    elif config.true('_KEEP_ALIVE'):
        keep_alive=True
        block_limit = -1

    if session_block_offset == -1:
        session_block_offset = block_offset
    elif not config.true('_KEEP_ALIVE'):
        if block_limit == 0:
            block_limit = block_offset

    queue_adapter = ChaindFsAdapter(
        chain_spec,
        config.get('SESSION_DATA_DIR'),
        EthCacheTx,
        None,
        )
    fltr = StateFilter(queue_adapter)
    sync_store = SyncFsStore(config.get('SESSION_RUNTIME_DIR'), session_id=config.get('SESSION_ID'))
    sync_store.register(fltr)

    chain_interface = EthChainInterface()
    drv = ChainInterfaceDriver(sync_store, chain_interface, offset=session_block_offset, target=block_limit)
    drv.run(conn)
   

if __name__ == '__main__':
    main()
