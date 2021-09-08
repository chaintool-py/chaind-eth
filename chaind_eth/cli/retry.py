# standard imports
import logging

# external imports
from chainlib.eth.gas import price
from chainlib.eth.tx import unpack
from chaind.error import TxSourceError
from crypto_dev_signer.eth.transaction import EIP155Transaction
from chainlib.eth.gas import Gas
from hexathon import (
        add_0x,
        strip_0x,
        )

# local imports
from chaind_eth.cli.tx import TxProcessor

logg = logging.getLogger(__name__)

DEFAULT_GAS_FACTOR = 1.1


class Retrier:

    def __init__(self, sender, signer, source, chain_spec, gas_oracle, gas_factor=DEFAULT_GAS_FACTOR):
        self.sender = sender
        self.signer = signer
        self.source = source
        self.raw_content = []
        self.content = []
        self.cursor = 0
        self.gas_oracle = gas_oracle
        self.gas_factor = gas_factor
        self.chain_spec = chain_spec
        self.chain_id = chain_spec.chain_id()
        self.processor = [TxProcessor()]


    def load(self, process=True):
        for processor in self.processor:
            self.raw_content = processor.load(self.source)
        if self.raw_content != None:
            if process:
                #try:
                self.process()
                #except Exception as e:
                #    raise TxSourceError('invalid source contents: {}'.format(str(e)))
            return self.content
        raise TxSourceError('unparseable source')
       

    def process(self):
        gas_data = self.gas_oracle.get_gas()
        gas_price = gas_data[0]
        for tx in self.raw_content:
            tx_bytes = bytes.fromhex(strip_0x(tx))
            tx = unpack(tx_bytes, self.chain_spec)
            tx_gas_price_old = int(tx['gasPrice'])
            if tx_gas_price_old < gas_price:
                tx['gasPrice'] = gas_price
            else:
                tx['gasPrice'] = int(tx_gas_price_old * self.gas_factor)
            if tx_gas_price_old == tx['gasPrice']:
                tx['gasPrice'] += 1
            tx_obj = EIP155Transaction(tx, tx['nonce'], self.chain_id)
            new_tx_bytes = self.signer.sign_transaction_to_wire(tx_obj)
            logg.debug('add tx {} with gas price changed from {} to {}: {}'.format(tx['hash'], tx_gas_price_old, tx['gasPrice'], new_tx_bytes.hex()))
            self.content.append(new_tx_bytes)


    def __iter__(self):
        self.cursor = 0
        return self


    def __next__(self): 
        if self.cursor == len(self.content):
            raise StopIteration()
        tx = self.content[self.cursor]
        self.cursor += 1
        return tx
