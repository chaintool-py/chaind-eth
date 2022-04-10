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
from chaind.setup import Environment
from chainlib.eth.gas import price
from chainlib.chain import ChainSpec
from hexathon import strip_0x

# local imports
from chaind.error import TxSourceError
from chaind.eth.token.process import Processor
from chaind.eth.token.gas import GasTokenResolver
from chaind.eth.cli.csv import CSVProcessor
from chaind.eth.cli.output import (
        Outputter,
        OpMode,
        )

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__)) 
config_dir = os.path.join(script_dir, '..', 'data', 'config')


arg_flags = chainlib.eth.cli.argflag_std_write
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)
argparser.add_argument('--socket', dest='socket', type=str, help='Socket to send transactions to')
argparser.add_argument('--token-module', dest='token_module', type=str, help='Python module path to resolve tokens from identifiers')
argparser.add_positional('source', required=False, type=str, help='Transaction source file')
args = argparser.parse_args()

extra_args = {
        'socket': None,
        'source': None,
        }
env = Environment(domain='eth', env=os.environ)
config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=config_dir)
config.add(args.token_module, 'TOKEN_MODULE', True)

wallet = chainlib.eth.cli.Wallet()
wallet.from_config(config)

rpc = chainlib.eth.cli.Rpc(wallet=wallet)
conn = rpc.connect_by_config(config)

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

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


def main():
    token_resolver = None
    if config.get('TOKEN_MODULE') != None:
        import importlib
        m = importlib.import_module(config.get('TOKEN_MODULE'))
        m = m.TokenResolver
    else:
        from chaind.eth.token.gas import GasTokenResolver
        m = GasTokenResolver
    token_resolver = m(chain_spec, rpc.get_sender_address(), rpc.get_signer(), rpc.get_gas_oracle(), rpc.get_nonce_oracle())
    
    processor = Processor(token_resolver, config.get('_SOURCE'))
    processor.add_processor(CSVProcessor())

    sends = None
    try:
        sends = processor.load(conn)
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
