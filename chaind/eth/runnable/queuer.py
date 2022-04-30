# standard imports
import os
import logging
import signal

# external imports
import chainlib.eth.cli
import chaind.cli
import chainqueue.cli
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
from chaind.eth.settings import ChaindEthSettings

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '..', 'data', 'config')

env = Environment(domain='eth', env=os.environ)

arg_flags = chainlib.eth.cli.argflag_std_read
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)

queue_arg_flags = 0
chainqueue.cli.process_flags(argparser, queue_arg_flags)

local_arg_flags = chaind.cli.argflag_local_base | chaind.cli.ChaindFlag.DISPATCH | chaind.cli.ChaindFlag.SOCKET
chaind.cli.process_flags(argparser, local_arg_flags)

args = argparser.parse_args()

base_config_dir = [chainqueue.cli.config_dir, chaind.cli.config_dir]
config = chainlib.eth.cli.Config.from_args(args, arg_flags, base_config_dir=base_config_dir)
config = chaind.cli.process_config(config, args, local_arg_flags)
config = chainqueue.cli.process_config(config, args, queue_arg_flags)
config.add('eth', 'CHAIND_ENGINE', False)
config.add('queue', 'CHAIND_COMPONENT', False)
logg.debug('config loaded:\n{}'.format(config))

settings = ChaindEthSettings(include_queue=True)
settings.process(config)

logg.debug('settings:\n{}'.format(settings))


def process_outgoing(chain_spec, adapter, rpc, limit=50):
    adapter = None
    process_err = None
    for i in range(2):
        try:
            adapter = ChaindFsAdapter(
                settings.get('CHAIN_SPEC'),
                settings.dir_for('queue'),
                EthCacheTx,
                dispatcher,
                )
        except BackendIntegrityError as e:
            process_err = e
            continue

    if adapter == None:
        raise BackendIntegrityError(process_err)
    
    upcoming = adapter.upcoming(limit=limit)
    logg.info('processor has {} candidates for {}, processing with limit {} adapter {} rpc {}'.format(len(upcoming), chain_spec, limit, adapter, rpc))
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
        settings.get('CHAIN_SPEC'),
        settings.dir_for('queue'),
        EthCacheTx,
        dispatcher,
        )

ctrl = SessionController(settings, queue_adapter, process_outgoing)
signal.signal(signal.SIGINT, ctrl.shutdown)
signal.signal(signal.SIGTERM, ctrl.shutdown)

logg.info('session id is ' + settings.get('SESSION_ID'))
logg.info('session socket path is ' + settings.get('SESSION_SOCKET_PATH'))

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
