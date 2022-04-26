# external imports
from chainlib.eth.connection import EthHTTPConnection
from chaind.settings import ChaindSettings
from chaind.eth.chain import EthChainInterface


class ChaindEthSettings(ChaindSettings):

    def process_sync_interface(self, config):
        self.o['SYNCER_INTERFACE'] = EthChainInterface()


    def process_common(self, config):
        super(ChaindEthSettings, self).process_common(config)
        rpc_provider = config.get('RPC_PROVIDER')
        if rpc_provider == None:
            rpc_provider = 'http://localhost:8545'
        self.o['RPC'] = EthHTTPConnection(url=rpc_provider, chain_spec=self.o['CHAIN_SPEC'])
