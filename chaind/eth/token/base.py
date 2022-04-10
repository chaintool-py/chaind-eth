# standard imports
import logging

# external imports
from funga.eth.transaction import EIP155Transaction
from hexathon import strip_0x

logg = logging.getLogger(__name__)

class BaseTokenResolver:

    def __init__(self, chain_spec, sender, signer, gas_oracle, nonce_oracle):
        self.chain_spec = chain_spec
        self.chain_id = chain_spec.chain_id()
        self.signer = signer
        self.sender = sender
        self.gas_oracle = gas_oracle
        self.nonce_oracle = nonce_oracle
        self.factory = None
        self.gas_limit_start = None
        self.gas_price_start = None

    
    def reset(self):
        gas_data = self.gas_oracle.get_gas()
        self.gas_price_start = gas_data[0]
        self.gas_limit_start = gas_data[1]


    def get_values(self, gas_value, value, executable_address=None):
        if executable_address == None:
            return (value, 0)

        try:
            value = int(value)
        except ValueError:
            value = int(strip_0x(value), 16)

        try:
            gas_value = int(gas_value)
        except ValueError:
            gas_value = int(strip_0x(gas_value), 16)

        nonce = self.nonce_oracle.next_nonce()

        return (gas_value, value, nonce,)


    def sign(self, tx):
        tx_o = EIP155Transaction(tx, tx['nonce'], self.chain_id)
        tx_bytes = self.signer.sign_transaction_to_wire(tx_o)
        return tx_bytes
