# external imports
from eth_erc20 import ERC20
from chainlib.eth.tx import TxFormat

# local imports
from chaind.eth.token import BaseTokenResolver


class TokenResolver(BaseTokenResolver):

    def __init__(self, chain_spec, sender, signer, gas_oracle, nonce_oracle):
        super(TokenResolver, self).__init__(chain_spec, sender, signer, gas_oracle, nonce_oracle)
        self.factory = ERC20(self.chain_spec, signer=self.signer, gas_oracle=self.gas_oracle, nonce_oracle=self.nonce_oracle)


    def create(self, conn, recipient, gas_value, data=None, token_value=0, executable_address=None, passphrase=None):

        if executable_address == None:
            raise ValueError('executable address required')

        (gas_value, token_value, nonce) = self.get_values(gas_value, token_value, executable_address=executable_address)

        tx = self.factory.transfer(executable_address, self.sender, recipient, token_value, tx_format=TxFormat.DICT)
        tx['value'] = gas_value

        return tx
