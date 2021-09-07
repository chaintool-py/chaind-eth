# standard imports
import logging

# external imports
from chaind.error import TxSourceError
from chainlib.eth.address import is_checksum_address
from chainlib.eth.tx import unpack
from chainlib.eth.gas import Gas
from hexathon import (
        add_0x,
        strip_0x,
        )
from crypto_dev_signer.eth.transaction import EIP155Transaction
from eth_erc20 import ERC20

logg = logging.getLogger(__name__)


class Processor:

    def __init__(self, sender, signer, source, chain_spec, gas_oracle, nonce_oracle, resolver=None):
        self.sender = sender
        self.signer = signer
        self.source = source
        self.processor = []
        self.content = []
        self.token_resolver = resolver
        self.cursor = 0
        self.gas_oracle = gas_oracle
        self.nonce_oracle = nonce_oracle
        self.nonce_start = None
        self.gas_limit_start = None
        self.gas_price_start = None
        self.chain_spec = chain_spec
        self.chain_id = chain_spec.chain_id()


    def add_processor(self, processor):
        self.processor.append(processor)


    def load(self, process=True):
        for processor in self.processor:
            self.content = processor.load(self.source)
        if self.content != None:
            if process:
                #try:
                self.process()
                #except Exception as e:
                #    raise TxSourceError('invalid source contents: {}'.format(str(e)))
            return self.content
        raise TxSourceError('unparseable source')
       
    
    # 0: recipient
    # 1: amount
    # 2: token identifier
    def process(self):
        txs = []
        for i, r in enumerate(self.content):
            logg.debug('processing {}'.format(r))
            if not is_checksum_address(r[0]):
                raise ValueError('invalid checksum address {} in record {}'.format(r[0], i))
            self.content[i][0] = add_0x(r[0])
            try:
                self.content[i][1] = int(r[1])
            except ValueError:
                self.content[i][1] = int(strip_0x(r[1]), 16)
            native_token_value = 0
            if self.token_resolver == None:
                self.content[i][2] = None
            else:
                k = r[2]
                self.content[i][2] = self.token_resolver.lookup(k)

            if len(self.content[i]) == 3:
                self.content[i].append(native_token_value)


    def __iter__(self):
        gas_data = self.gas_oracle.get_gas()
        self.gas_price_start = gas_data[0]
        self.gas_limit_start = gas_data[1]
        self.cursor = 0
        return self


    def __next__(self): 
        if self.cursor == len(self.content):
            raise StopIteration()

        nonce = self.nonce_oracle.next_nonce()

        token_factory = None

        r = self.content[self.cursor]
        logg.debug('rrrr {} '.format(r))
        if r[2] == None:
            token_factory = Gas(self.chain_spec, signer=self.signer, gas_oracle=self.gas_oracle, nonce_oracle=self.nonce_oracle)
        else:
            token_factory = ERC20(self.chain_spec, signer=self.signer, gas_oracle=self.gas_oracle, nonce_oracle=self.nonce_oracle)

        value = 0
        data = '0x'
        if isinstance(token_factory, ERC20):
            (tx_hash_hex, o) = token_factory.transfer(r[2], self.sender, r[0], r[1])
            logg.debug('tx {}'.format(o))
            # TODO: allow chainlib to return args only
            tx = unpack(bytes.fromhex(strip_0x(o['params'][0])), self.chain_spec)
            data = tx['data']
        else:
            value = r[1]

        tx = {
            'from': self.sender,
            'to': r[0],
            'value': value,
            'data': data,
            'nonce': nonce,
            'gasPrice': self.gas_price_start,
            'gas': self.gas_limit_start,
                }
        tx_o = EIP155Transaction(tx, nonce, self.chain_id)
        tx_bytes = self.signer.sign_transaction_to_wire(tx_o)
        self.cursor += 1
        return tx_bytes


    def __str__(self):
        names = []
        for s in self.processor:
            names.append(str(s))
        return ','.join(names)
