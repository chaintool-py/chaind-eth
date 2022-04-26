# standard imports
import os
import logging

# external imports
import chaind.cli
from chaind.setup import Environment
from chaind.filter import StateFilter
from chaind.adapters.fs import ChaindFsAdapter
from chainlib.eth.block import block_latest
from hexathon import strip_0x
from chainsyncer.store.fs import SyncFsStore
from chainsyncer.driver.chain_interface import ChainInterfaceDriver
from chaind.eth.settings import ChaindEthSettings

# local imports
from chaind.eth.cache import EthCacheTx

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '..', 'data', 'config')

env = Environment(domain='eth', env=os.environ)

arg_flags = chaind.cli.argflag_local_sync
argparser = chaind.cli.ArgumentParser(arg_flags)
local_arg_flags = chaind.cli.argflag_local_sync
argparser.process_local_flags(local_arg_flags)
args = argparser.parse_args()
config = chaind.cli.Config.from_args('eth', args, arg_flags, local_arg_flags)

logg.debug('config loaded:\n{}'.format(config))

settings = ChaindEthSettings()
settings.process(config)

logg.debug('settings:\n{}'.format(settings))


def main():
    queue_adapter = ChaindFsAdapter(
        settings.get('CHAIN_SPEC'),
        settings.get('SESSION_DATA_DIR'),
        EthCacheTx,
        None,
        )
    fltr = StateFilter(queue_adapter)
    sync_store = SyncFsStore(settings.get('SESSION_RUNTIME_DIR'), session_id=settings.get('SESSION_ID'))
    sync_store.register(fltr)

    logg.debug('session block offset {}'.format(settings.get('SYNCER_OFFSET')))

    drv = ChainInterfaceDriver(sync_store, settings.get('SYNCER_INTERFACE'), offset=settings.get('SYNCER_OFFSET'), target=settings.get('SYNCER_LIMIT'))
    drv.run(settings.get('RPC'))
   

if __name__ == '__main__':
    main()
