# standard imports
import os
import logging
import sys
import datetime
import enum
import re
import stat
import socket

# external imports
import chainlib.eth.cli
from chaind import Environment
from chainlib.eth.gas import price
from chainlib.chain import ChainSpec
from hexathon import strip_0x

# local imports
from chaind_eth.cli.process import Processor
from chaind_eth.cli.csv import CSVProcessor
from chaind.error import TxSourceError
from chaind_eth.cli.resolver import (
        DefaultResolver,
        LookNoop,
        TokenIndexLookup,
        )

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__)) 
config_dir = os.path.join(script_dir, '..', 'data', 'config')


arg_flags = chainlib.eth.cli.argflag_std_write
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)
argparser.add_argument('--socket', dest='socket', type=str, help='Socket to send transactions to')
argparser.add_argument('--token-index', dest='token_index', type=str, help='Token resolver index')
argparser.add_positional('source', required=False, type=str, help='Transaction source file')
args = argparser.parse_args()

extra_args = {
        'socket': None,
        'source': None,
        'token_index': None,
        }

env = Environment(domain='eth', env=os.environ)
config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=config_dir)

wallet = chainlib.eth.cli.Wallet()
wallet.from_config(config)

rpc = chainlib.eth.cli.Rpc(wallet=wallet)
conn = rpc.connect_by_config(config)

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

class OpMode(enum.Enum):
    STDOUT = 'standard_output'
    UNIX = 'unix_socket'
mode = OpMode.STDOUT

re_unix = r'^ipc://(/.+)'
m = re.match(re_unix, config.get('_SOCKET', ''))
if m != None:
    config.add(m.group(1), '_SOCKET', exists_ok=True)
    r = 0
    try:
        stat_info = os.stat(config.get('_SOCKET'))
        if not stat.S_ISSOCK(stat_info.st_mode):
            r = 1
    except FileNotFoundError:
        r = 1

    if r > 0:
        sys.stderr.write('{} is not a socket\n'.format(config.get('_SOCKET')))
        sys.exit(1)
    
    mode = OpMode.UNIX

logg.info('using mode {}'.format(mode.value))

if config.get('_SOURCE') == None:
    sys.stderr.write('source data missing\n')
    sys.exit(1)


class Outputter:

    def __init__(self, mode):
        self.out = getattr(self, 'do_' + mode.value)


    def do(self, hx):
        return self.out(hx)


    def do_standard_output(self, hx):
        #sys.stdout.write(hx + '\n')
        return hx


    def do_unix_socket(self, hx):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(config.get('_SOCKET'))
        s.send(hx.encode('utf-8'))
        r = s.recv(64+4)
        logg.debug('r {}'.format(r))
        s.close()
        return r[4:].decode('utf-8')


def main():
    signer = rpc.get_signer()


    # TODO: make resolvers pluggable
    token_resolver = DefaultResolver(chain_spec, conn, sender_address=rpc.get_sender_address())

    noop_lookup = LookNoop(check=not config.true('_UNSAFE'))
    token_resolver.add_lookup(noop_lookup, 'noop')
  
    if config.get('_TOKEN_INDEX') != None:
        token_index_lookup = TokenIndexLookup(chain_spec, signer, rpc.get_gas_oracle(), rpc.get_nonce_oracle(), config.get('_TOKEN_INDEX'))
        token_resolver.add_lookup(token_index_lookup, reverse=config.get('_TOKEN_INDEX'))
    
    processor = Processor(wallet.get_signer_address(), wallet.get_signer(), config.get('_SOURCE'), chain_spec, rpc.get_gas_oracle(), rpc.get_nonce_oracle(), resolver=token_resolver)
    processor.add_processor(CSVProcessor())

    sends = None
    try:
        sends = processor.load()
    except TxSourceError as e:
        sys.stderr.write('processing error: {}. processors: {}\n'.format(str(e), str(processor)))
        sys.exit(1)


    tx_iter = iter(processor)
    out = Outputter(mode)
    while True:
        tx = None
        try:
            tx_bytes = next(tx_iter)
        except StopIteration:
            break
        tx_hex = tx_bytes.hex()
        print(out.do(tx_hex))


if __name__ == '__main__':
    main()
