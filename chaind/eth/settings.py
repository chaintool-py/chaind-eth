# external imports
from chainlib.eth.connection import EthHTTPConnection
from chainlib.eth.settings import process_settings as base_process_settings
from chaind.eth.chain import EthChainInterface
from chaind.settings import *
from chainsyncer.settings import process_sync_range


def process_common(settings, config):
    rpc_provider = config.get('RPC_PROVIDER')
    if rpc_provider == None:
        rpc_provider = 'http://localhost:8545'
    conn = EthHTTPConnection(url=rpc_provider, chain_spec=settings.get('CHAIN_SPEC'))
    settings.set('RPC', conn)
    return settings


def process_sync(settings, config):
    settings.set('SYNCER_INTERFACE', EthChainInterface())
    settings = process_sync_range(settings, config)
    return settings


def process_settings(settings, config):
    settings = base_process_settings(settings, config)
    settings = process_common(settings, config)
    settings = process_backend(settings, config)
    settings = process_session(settings, config)
    settings = process_socket(settings, config)
    settings = process_token(settings, config)

    return settings
