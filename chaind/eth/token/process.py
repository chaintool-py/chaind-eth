# standard imports
import logging

# external imports
from chaind.error import TxSourceError
from chainlib.eth.address import (
        is_checksum_address,
        to_checksum_address,
        )
from chainlib.eth.tx import unpack
from chainlib.eth.gas import Gas
from hexathon import (
        add_0x,
        strip_0x,
        )
from funga.eth.transaction import EIP155Transaction

logg = logging.getLogger(__name__)


class Processor:

    def __init__(self, resolver, source, use_checksum=True):
        self.resolver = resolver
        self.source = source
        self.processor = []
        self.safe = use_checksum
        self.conn = None
        

    def add_processor(self, processor):
        self.processor.append(processor)


    def load(self, conn, process=True):
        self.conn = conn
        for processor in self.processor:
            self.content = processor.load(self.source)
        if self.content != None:
            if process:
                try:
                    self.process()
                except Exception as e:
                    raise TxSourceError('invalid source contents: {}'.format(str(e)))
            return self.content
        raise TxSourceError('unparseable source')
       
    
    # 0: recipient
    # 1: amount
    # 2: token identifier (optional, when not specified network gas token will be used)
    # 3: gas amount (optional)
    def process(self):
        txs = []
        for i, r in enumerate(self.content):
            logg.debug('processing {}'.format(r))
            address = r[0]
            if self.safe:
                if not is_checksum_address(address):
                    raise ValueError('invalid checksum address {} in record {}'.format(address, i))
            else:
                address = to_checksum_address(address)

            self.content[i][0] = add_0x(address)
            try:
                self.content[i][1] = int(r[1])
            except ValueError:
                self.content[i][1] = int(strip_0x(r[1]), 16)
            native_token_value = 0

            if len(self.content[i]) == 3:
                self.content[i].append(native_token_value)


    def __iter__(self):
        self.resolver.reset()
        self.cursor = 0
        return self


    def __next__(self): 
        if self.cursor == len(self.content):
            raise StopIteration()

        r = self.content[self.cursor]

        value = r[1]
        gas_value = 0
        try:
            gas_value = r[3]
        except IndexError:
            pass
        logg.debug('gasvalue {}'.format(gas_value))
        data = '0x'

        executable_address = None
        try:
            executable_address = r[2]
        except IndexError:
            pass

        tx = self.resolver.create(self.conn, r[0], gas_value, data=data, token_value=value, executable_address=executable_address)
        v =  self.resolver.sign(tx)

        self.cursor += 1

        return v


    def __str__(self):
        names = []
        for s in self.processor:
            names.append(str(s))
        return ','.join(names)
