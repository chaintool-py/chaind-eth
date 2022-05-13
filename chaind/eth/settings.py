# external imports
from chainlib.eth.connection import EthHTTPConnection
from chainlib.settings import process_settings as base_process_settings
from chaind.eth.chain import EthChainInterface
from chaind.settings import *


def process_sync_interface(settings, config):
    settings.set('SYNCER_INTERFACE', EthChainInterface())
    return settings


def process_common(settings, config):
    rpc_provider = config.get('RPC_PROVIDER')
    if rpc_provider == None:
        rpc_provider = 'http://localhost:8545'
    conn = EthHTTPConnection(url=rpc_provider, chain_spec=settings.get('CHAIN_SPEC'))
    settings.set('RPC', conn)
    return settings


def process_settings(settings, config):
    settings = base_process_settings(settings, config)
    settings = process_common(settings, config)
    settings = process_sync_interface(settings, config)

    if settings.include_queue:
        settings = process_queue_backend(settings, config)
    if settings.include_sync:
        settings = process_sync_backend(settings, config)

    settings = process_backend(settings, config)
    settings = process_session(settings, config)

    if settings.include_sync:
        settings = process_sync(settings, config)
    if settings.include_queue:
        settings = process_chaind_queue(settings, config)
        settings = process_dispatch(settings, config)
        settings = process_token(settings, config)

    settings = process_socket(settings, config)

    return settings
