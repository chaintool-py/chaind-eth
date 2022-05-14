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
from chainlib.eth.cli.arg import (
        Arg,
        ArgFlag,
        process_args,
        )
from chainlib.eth.cli.config import (
        Config,
        process_config,
        )
from chaind.setup import Environment
from chainlib.eth.gas import price
from chainlib.chain import ChainSpec
from hexathon import strip_0x
from chainqueue.cli.arg import (
        apply_arg as apply_arg_queue,
        apply_flag as apply_flag_queue,
        )
from chainqueue.data import config_dir as chainqueue_config_dir
from chaind.data import config_dir as chaind_config_dir
from chaind.cli.arg import (
        apply_arg,
        apply_flag,
        )
from chainlib.eth.cli.log import process_log
from chaind.settings import process_queue
from chaind.settings import ChaindSettings
from chaind.error import TxSourceError
from chainlib.error import (
        InitializationError,
        SignerMissingException,
        )
from chaind.cli.config import process_config as process_config_local

# local imports
from chaind.eth.token.process import Processor
from chaind.eth.token.gas import GasTokenResolver
from chaind.eth.cli.csv import CSVProcessor
from chaind.eth.cli.output import (
        Outputter,
        OpMode,
        )
from chaind.eth.settings import process_settings

logg = logging.getLogger()


def process_settings_local(settings, config):
#    if settings.get('SIGNER') == None:
#        raise SignerMissingException('signer missing')
    return settings


env = Environment(domain='eth', env=os.environ)

arg_flags = ArgFlag()
arg_flags = apply_flag_queue(arg_flags)
arg_flags = apply_flag(arg_flags)

arg = Arg(arg_flags)
arg = apply_arg_queue(arg)
arg = apply_arg(arg)
arg.set_long('s', 'send-rpc')

flags = arg_flags.STD_WRITE | arg_flags.TOKEN | arg_flags.SOCKET_CLIENT | arg_flags.STATE | arg_flags.WALLET | arg_flags.SESSION

argparser = chainlib.eth.cli.ArgumentParser()
argparser = process_args(argparser, arg, flags)
argparser.add_argument('source', help='Transaction source file')
args = argparser.parse_args()

logg = process_log(args, logg)

config = Config()
config.add_schema_dir(chainqueue_config_dir)
config.add_schema_dir(chaind_config_dir)
config = process_config(config, arg, args, flags)
config = process_config_local(config, arg, args, flags)
config.add(args.source, '_SOURCE', False)
config.add('queue', 'CHAIND_COMPONENT', False)
config.add('eth', 'CHAIND_ENGINE', False)
logg.debug('config loaded:\n{}'.format(config))

try:
    settings = ChaindSettings(include_sync=True)
    settings = process_settings(settings, config)
    settings = process_queue(settings, config)
    settings = process_settings_local(settings, config)
except InitializationError as e:
    sys.stderr.write('Initialization error: ' + str(e) + '\n')
    sys.exit(1)
logg.debug('settings loaded:\n{}'.format(settings))

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
        err = None
        try:
            s.connect(self.path)
        except FileNotFoundError as e:
            err = e
        if err != None:
            s.close()
            raise err
        s.sendall(tx.encode('utf-8'))
        r = s.recv(68)
        s.close()
        return r


def main():
    conn = settings.get('CONN')
    token_resolver = None
    if settings.get('TOKEN_MODULE') != None:
        import importlib
        m = importlib.import_module(settings.get('TOKEN_MODULE'))
        m = m.TokenResolver
    else:
        from chaind.eth.token.gas import GasTokenResolver
        m = GasTokenResolver
    token_resolver = m(
            settings.get('CHAIN_SPEC'),
            settings.get('SENDER_ADDRESS'),
            settings.get('SIGNER'),
            settings.get('GAS_ORACLE'),
            settings.get('NONCE_ORACLE'),
            )
    
    processor = Processor(token_resolver, config.get('_SOURCE'), use_checksum=not config.get('_UNSAFE'))
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
            r = None
            try:
                r = sender.send(tx_hex)
            except FileNotFoundError as e:
                sys.stderr.write('send to socket {} failed: {}\n'.format(sender.path, e))
                sys.exit(1)
            logg.info('sent {} result {}'.format(tx_hex, r))
        print(out.do(tx_hex))


if __name__ == '__main__':
    main()
