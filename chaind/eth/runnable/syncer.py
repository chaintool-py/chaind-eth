# standard imports
import os
import logging

# external imports
import chainlib.eth.cli
from chaind.setup import Environment
from chaind.filter import StateFilter
from chainlib.eth.block import block_latest
from hexathon import strip_0x
from chainsyncer.store.fs import SyncFsStore
from chainsyncer.driver.chain_interface import ChainInterfaceDriver
from chainsyncer.error import SyncDone
from chainlib.eth.cli.arg import (
        Arg,
        ArgFlag,
        process_args,
        )
from chainlib.eth.cli.config import (
        Config,
        process_config,
        )
from chainsyncer.cli.arg import (
        apply_arg as apply_arg_sync,
        apply_flag as apply_flag_sync,
        )
from chainsyncer.data import config_dir as chainsyncer_config_dir
from chaind.data import config_dir as chaind_config_dir
from chaind.cli.arg import (
        apply_arg,
        apply_flag,
        )
from chainlib.eth.cli.log import process_log
from chaind.settings import ChaindSettings
from chaind.cli.config import process_config as process_config_local
from chainsyncer.cli.config import process_config as process_config_syncer

# local imports
from chaind.eth.cache import EthCacheTx
from chaind.eth.settings import (
    process_settings,
    process_sync,
    )


logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '..', 'data', 'config')

env = Environment(domain='eth', env=os.environ)

arg_flags = ArgFlag()
arg_flags = apply_flag_sync(arg_flags)
arg_flags = apply_flag(arg_flags)

arg = Arg(arg_flags)
arg = apply_arg_sync(arg)
arg = apply_arg(arg)

flags = arg_flags.STD_BASE | arg_flags.CHAIN_SPEC | arg_flags.PROVIDER | arg_flags.SEQ | arg_flags.STATE
flags = arg_flags.more(flags, arg_flags.SYNC_RANGE_EXT)
flags = arg_flags.more(flags, arg_flags.CHAIND_BASE)

argparser = chainlib.eth.cli.ArgumentParser()
argparser = process_args(argparser, arg, flags)
args = argparser.parse_args()

logg = process_log(args, logg)

config = Config()
config.add_schema_dir(chainsyncer_config_dir)
config.add_schema_dir(chaind_config_dir)
config = process_config(config, arg, args, flags)
config = process_config_local(config, arg, args, flags)
config = process_config_syncer(config, arg, args, flags)
config.add('eth', 'CHAIND_ENGINE', False)
config.add('sync', 'CHAIND_COMPONENT', False)
logg.debug('config loaded:\n{}'.format(config))

settings = ChaindSettings(include_sync=True)
settings = process_settings(settings, config)
settings = process_sync(settings, config)
logg.debug('settings loaded:\n{}'.format(settings))


def main():
    fltr = StateFilter(settings.get('CHAIN_SPEC'), settings.dir_for('queue'), EthCacheTx)
    sync_store = SyncFsStore(settings.get('SESSION_DATA_PATH'), session_id=settings.get('SESSION_ID'))
    sync_store.register(fltr)

    logg.debug('session block offset {}'.format(settings.get('SYNCER_OFFSET')))

    drv = ChainInterfaceDriver(sync_store, settings.get('SYNCER_INTERFACE'), offset=settings.get('SYNCER_OFFSET'), target=settings.get('SYNCER_LIMIT'))
    try:
        drv.run(settings.get('CONN'))
    except SyncDone as e:
        logg.info('sync done: {}'.format(e))
   

if __name__ == '__main__':
    main()
