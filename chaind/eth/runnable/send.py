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
import chaind.cli
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
from chaind.eth.settings import ChaindEthSettings

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

arg_flags = chainlib.eth.cli.argflag_std_write
argparser = chainlib.eth.cli.ArgumentParser(arg_flags, arg_long={'-s': '--send-rpc'})
argparser.add_positional('source', required=False, type=str, help='Transaction source file')

local_arg_flags = chaind.cli.argflag_local_socket_client
chaind.cli.process_flags(argparser, local_arg_flags)

args = argparser.parse_args()

env = Environment(domain='eth', env=os.environ)

base_config_dir = [chaind.cli.config_dir]
config = chainlib.eth.cli.Config.from_args(args, arg_flags, base_config_dir=base_config_dir)
config = chaind.cli.process_config(config, args, local_arg_flags)
config.add(args.source, '_SOURCE', False)
config.add('eth', 'CHAIND_ENGINE', False)
config.add('queue', 'CHAIND_COMPONENT', False)
logg.debug('config loaded:\n{}'.format(config))

wallet = chainlib.eth.cli.Wallet()
wallet.from_config(config)

settings = ChaindEthSettings(include_queue=True)
settings.process(config)

logg.debug('settings:\n{}'.format(settings))

rpc = chainlib.eth.cli.Rpc(wallet=wallet)
conn = rpc.connect_by_config(config)

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

mode = OpMode.STDOUT

re_unix = r'^ipc://(/.+)'
m = re.match(re_unix, config.get('SESSION_SOCKET_PATH', ''))
if m != None:
    config.add(m.group(1), 'SESSION_SOCKET_PATH', exists_ok=True)
    r = 0
    try:
        stat_info = os.stat(config.get('SESSION_SOCKET_PATH'))
        if not stat.S_ISSOCK(stat_info.st_mode):
            r = 1
    except FileNotFoundError:
        r = 1

    if r > 0:
        sys.stderr.write('{} is not a socket\n'.format(config.get('SESSION_SOCKET_PATH')))
        sys.exit(1)
    
    mode = OpMode.UNIX

logg.info('using mode {}'.format(mode.value))

if config.get('_SOURCE') == None:
    sys.stderr.write('source data missing\n')
    sys.exit(1)


class SocketSender:

    def __init__(self, settings):
        self.path = settings.get('SESSION_SOCKET_PATH')

    def send(self, tx):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.path)
        s.sendall(tx.encode('utf-8'))
        r = s.recv(68)
        s.close()
        return r


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

    sender = None
    if config.true('_SOCKET_SEND'):
        if settings.get('SESSION_SOCKET_PATH') != None:
            sender = SocketSender(settings)

    tx_iter = iter(processor)
    out = Outputter(mode)
    while True:
        tx = None
        try:
            tx_bytes = next(tx_iter)
        except StopIteration:
            break
        tx_hex = tx_bytes.hex()
        if sender != None:
            r = sender.send(tx_hex)
            logg.info('sent {} result {}'.format(tx_hex, r))
        print(out.do(tx_hex))


if __name__ == '__main__':
    main()
