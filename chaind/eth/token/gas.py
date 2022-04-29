# external imports
from chainlib.eth.gas import Gas
from hexathon import strip_0x

# local imports
from chaind.eth.token import BaseTokenResolver


class GasTokenResolver(BaseTokenResolver):

    def __init__(self, chain_spec, sender, signer, gas_oracle, nonce_oracle):
        super(GasTokenResolver, self).__init__(chain_spec, sender, signer, gas_oracle, nonce_oracle, advance_nonce=True)
        self.factory = Gas(self.chain_spec, signer=self.signer, gas_oracle=self.gas_oracle, nonce_oracle=self.nonce_oracle)


    def create(self, conn, recipient, gas_value, data=None, token_value=0, executable_address=None, passphrase=None):

        (gas_value, token_value, nonce) = self.get_values(gas_value, token_value, executable_address=executable_address)

        tx = {
            'from': self.sender,
            'to': recipient,
            'value': gas_value,
            'data': data,
            'nonce': nonce,
            'gasPrice': self.gas_price_start,
            'gas': self.gas_limit_start,
                }

        return tx
