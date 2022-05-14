# standard imports
import os
import logging
import signal

# external imports
import chainlib.eth.cli
from chainlib.eth.cli.arg import (
        Arg,
        ArgFlag,
        process_args,
        )
from chainlib.eth.cli.config import (
        Config,
        process_config,
        )
from chainqueue.cli.arg import (
        apply_arg as apply_arg_queue,
        apply_flag as apply_flag_queue,
        )
from chaind.cli.arg import (
        apply_arg,
        apply_flag,
        )
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
from chaind.dispatch import DispatchProcessor
from chainqueue.data import config_dir as chainqueue_config_dir
from chaind.data import config_dir as chaind_config_dir
from chainlib.eth.cli.log import process_log
from chaind.cli.config import process_config as process_config_local

# local imports
from chaind.eth.cache import EthCacheTx
from chaind.eth.settings import ChaindSettings
from chaind.eth.dispatch import EthDispatcher
from chaind.eth.settings import process_settings
from chaind.settings import (
        process_queue,
        process_socket,
        process_dispatch,
        )

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '..', 'data', 'config')

env = Environment(domain='eth', env=os.environ)

arg_flags = ArgFlag()
arg_flags = apply_flag_queue(arg_flags)
arg_flags = apply_flag(arg_flags)

arg = Arg(arg_flags)
arg = apply_arg_queue(arg)
arg = apply_arg(arg)

flags = arg_flags.STD_READ | arg_flags.QUEUE | arg_flags.STATE | arg_flags.SESSION

argparser = chainlib.eth.cli.ArgumentParser()
argparser = process_args(argparser, arg, flags)
args = argparser.parse_args()

logg = process_log(args, logg)

config = Config()
config.add_schema_dir(chainqueue_config_dir)
config.add_schema_dir(chaind_config_dir)
config = process_config(config, arg, args, flags)
config = process_config_local(config, arg, args, flags)
config.add('eth', 'CHAIND_ENGINE', False)
config.add('sync', 'CHAIND_COMPONENT', False)
logg.debug('config loaded:\n{}'.format(config))

settings = ChaindSettings(include_sync=True)
settings = process_settings(settings, config)
settings = process_queue(settings, config)
settings = process_socket(settings, config)
settings = process_dispatch(settings, config)
logg.debug('settings loaded:\n{}'.format(settings))

tx_normalizer = TxHexNormalizer().tx_hash
token_cache_store = CacheTokenTx(settings.get('CHAIN_SPEC'), normalizer=tx_normalizer)

dispatcher = EthDispatcher(settings.get('CONN'))
processor = DispatchProcessor(settings.get('CHAIN_SPEC'), settings.dir_for('queue'), dispatcher)
ctrl = SessionController(settings, processor.process)

signal.signal(signal.SIGINT, ctrl.shutdown)
signal.signal(signal.SIGTERM, ctrl.shutdown)

logg.info('session id is ' + settings.get('SESSION_ID'))
logg.info('session socket path is ' + settings.get('SESSION_SOCKET_PATH'))


def main():
    global dispatcher, settings

    queue_adapter = ChaindFsAdapter(
        settings.get('CHAIN_SPEC'),
        settings.dir_for('queue'),
        EthCacheTx,
        dispatcher,
        store_sync=False,
        )

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
            ctrl.process(settings.get('CONN'))
            #queue_adapter = create_adapter(settings, dispatcher)
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
