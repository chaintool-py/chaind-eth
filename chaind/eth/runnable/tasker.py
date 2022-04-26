# standard imports
import os
import logging
import signal

# external imports
import chainlib.eth.cli
from chaind.session import SessionController
from chaind.setup import Environment
from chaind.error import (
        NothingToDoError,
        ClientGoneError,
        ClientBlockError,
        ClientInputError,
        )
from chainqueue import (
        Store,
        Status,
        )
from chainqueue.error import DuplicateTxError
from chainqueue.store.fs import (
        IndexStore,
        CounterStore,
        )
from chainqueue.cache import CacheTokenTx
from chainlib.encode import TxHexNormalizer
from chainlib.chain import ChainSpec
from chaind.adapters.fs import ChaindFsAdapter

# local imports
from chaind.eth.dispatch import EthDispatcher
from chaind.eth.cache import EthCacheTx

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

logg.debug('config loaded:\n{}'.format(config))

def process_outgoing(chain_spec, adapter, rpc, limit=100):
    upcoming = adapter.upcoming()
    logg.info('process {} {} {}'.format(chain_spec, adapter, rpc))
    logg.info('upcoming {}'.format(upcoming))
    i = 0
    for tx_hash in upcoming:
        if adapter.dispatch(tx_hash):
            i += 1
    return i

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

rpc = chainlib.eth.cli.Rpc()
conn = rpc.connect_by_config(config)

tx_normalizer = TxHexNormalizer().tx_hash
token_cache_store = CacheTokenTx(chain_spec, normalizer=tx_normalizer)
dispatcher = EthDispatcher(conn)
queue_adapter = ChaindFsAdapter(
        chain_spec,
        config.get('SESSION_DATA_DIR'),
        EthCacheTx,
        dispatcher,
        )

ctrl = SessionController(config, queue_adapter, process_outgoing)
signal.signal(signal.SIGINT, ctrl.shutdown)
signal.signal(signal.SIGTERM, ctrl.shutdown)

logg.info('session id is ' + config.get('SESSION_ID'))
logg.info('session socket path is ' + config.get('SESSION_SOCKET_PATH'))

def main():
    while True:
        v = None
        client_socket = None
        try:
            (client_socket, v) = ctrl.get()
        except ClientGoneError:
            break
        except ClientBlockError:
            continue
        except ClientInputError:
            continue
        except NothingToDoError:
            pass

        if v == None:
            ctrl.process(conn)
            continue

        result_data = None
        r = 0 # no error
        try:
            result_data = queue_adapter.put(v.hex())
        except DuplicateTxError as e:
            logg.error('tx already exists: {}'.format(e))
            r = 1
        except ValueError as e:
            logg.error('adapter rejected input {}: "{}"'.format(v.hex(), e))
            continue

        if r == 0:
            queue_adapter.enqueue(result_data)

        ctrl.respond_put(client_socket, r, extra_data=result_data)
        

if __name__ == '__main__':
    main()
