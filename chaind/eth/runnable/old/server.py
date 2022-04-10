# standard imports
import sys
import time
import socket
import signal
import os
import logging
import stat
import argparse

# external imports
import chainlib.eth.cli
from chaind import Environment
from hexathon import strip_0x
from chainlib.chain import ChainSpec
from chainlib.eth.connection import EthHTTPConnection
from chainqueue.sql.backend import SQLBackend
from chainlib.error import JSONRPCException
from chainqueue.db import dsn_from_config
from chaind.sql.session import SessionIndex

# local imports
from chaind_eth.dispatch import Dispatcher
from chainqueue.adapters.eth import EthAdapter

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__))
config_dir = os.path.join(script_dir, '..', 'data', 'config')

env = Environment(domain='eth', env=os.environ)

arg_flags = chainlib.eth.cli.argflag_std_read
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)
argparser.add_argument('--data-dir', type=str, help='data directory')
argparser.add_argument('--runtime-dir', type=str, help='runtime directory')
argparser.add_argument('--session-id', dest='session_id', type=str, help='session identifier')
argparser.add_argument('--dispatch-delay', dest='dispatch_delay', type=float, help='socket timeout before processing queue')
args = argparser.parse_args()
extra_args = {
    'runtime_dir': 'SESSION_RUNTIME_DIR',
    'data_dir': 'SESSION_DATA_DIR',
    'session_id': 'SESSION_ID', 
    'dispatch_delay': 'SESSION_DISPATCH_DELAY',
        }
#config = chainlib.eth.cli.Config.from_args(args, arg_flags, default_config_dir=config_dir, extend_base_config_dir=config_dir)
config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=config_dir)

logg.debug('session id {} {}'.format(type(config.get('SESSION_ID')), config.get('SESSION_ID')))
if config.get('SESSION_ID') == None:
    config.add(env.session, 'SESSION_ID', exists_ok=True)
if config.get('SESSION_RUNTIME_DIR') == None:
    config.add(env.runtime_dir, 'SESSION_RUNTIME_DIR', exists_ok=True)
if config.get('SESSION_DATA_DIR') == None:
    config.add(env.data_dir, 'SESSION_DATA_DIR', exists_ok=True)
if not config.get('SESSION_SOCKET_PATH'):
    socket_path = os.path.join(config.get('SESSION_RUNTIME_DIR'), config.get('SESSION_ID'), 'chaind.sock')
    config.add(socket_path, 'SESSION_SOCKET_PATH', True)

if config.get('DATABASE_ENGINE') == 'sqlite':
    #config.add(os.path.join(config.get('SESSION_DATA_DIR'), config.get('DATABASE_NAME') + '.sqlite'), 'DATABASE_NAME', exists_ok=True)
    config.add(os.path.join(config.get('SESSION_DATA_DIR'), config.get('DATABASE_NAME') + '.sqlite'), 'DATABASE_NAME', exists_ok=True)
    
config.censor('PASSWORD', 'DATABASE')
logg.debug('config loaded:\n{}'.format(config))


# verify setup
try:
    os.stat(config.get('DATABASE_NAME'))
except FileNotFoundError:
    sys.stderr.write('database file {} not found. please run database migration script first\n'.format(config.get('DATABASE_NAME')))
    sys.exit(1)


class SessionController:

    def __init__(self, config):
        self.dead = False
        os.makedirs(os.path.dirname(config.get('SESSION_SOCKET_PATH')), exist_ok=True)
        try:
            os.unlink(config.get('SESSION_SOCKET_PATH'))
        except FileNotFoundError:
            pass

        self.srv = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM)
        self.srv.bind(config.get('SESSION_SOCKET_PATH'))
        self.srv.listen(2)
        self.srv.settimeout(float(config.get('SESSION_DISPATCH_DELAY')))


    def shutdown(self, signo, frame):
        if self.dead:
            return
        self.dead = True
        if signo != None:
            logg.info('closing on {}'.format(signo))
        else:
            logg.info('explicit shutdown')
        sockname = self.srv.getsockname()
        self.srv.close()
        try:
            os.unlink(sockname)
        except FileNotFoundError:
            logg.warning('socket file {} already gone'.format(sockname))


    def get_connection(self):
        return self.srv.accept()


ctrl = SessionController(config)

signal.signal(signal.SIGINT, ctrl.shutdown)
signal.signal(signal.SIGTERM, ctrl.shutdown)

chain_spec = ChainSpec.from_chain_str(config.get('CHAIN_SPEC'))

rpc = chainlib.eth.cli.Rpc()
conn = rpc.connect_by_config(config)

dsn = dsn_from_config(config)
backend = SQLBackend(dsn, error_parser=rpc.error_parser, debug=config.true('DATABASE_DEBUG'))
session_index_backend = SessionIndex(config.get('SESSION_ID'))
adapter = EthAdapter(backend, session_index_backend=session_index_backend)


def process_outgoing(chain_spec, adapter, rpc, limit=100):
    dispatcher = Dispatcher(chain_spec, adapter, limit=limit)
    session = adapter.create_session()
    r = dispatcher.process(rpc, session)
    session.close()
    return r


def main():
    while True:
        srvs = None
        try:
            logg.debug('getting connection')
            (srvs, srvs_addr) = ctrl.get_connection()
        except OSError as e:
            try:
                fi = os.stat(config.get('SESSION_SOCKET_PATH'))
            except FileNotFoundError:
                logg.error('socket is gone')
                break
            if not stat.S_ISSOCK(fi.st_mode):
                logg.error('entity on socket path is not a socket')
                break
            if srvs == None:
                logg.debug('timeout (remote socket is none)')
                r = process_outgoing(chain_spec, adapter, conn)
                if r > 0:
                    ctrl.srv.settimeout(0.1)
                else:
                    ctrl.srv.settimeout(4.0)
                continue
        ctrl.srv.settimeout(0.1)
        srvs.settimeout(0.1)
        data_in = None
        try:
            data_in = srvs.recv(1048576)
        except BlockingIOError as e:
            logg.debug('block io error: {}'.format(e))
            continue

        data = None
        try:
            data_in_str = data_in.decode('utf-8')
            data_hex = strip_0x(data_in_str.rstrip())
            data = bytes.fromhex(data_hex)
        except ValueError:
            logg.error('invalid input "{}"'.format(data_in_str))
            continue

        logg.debug('recv {} bytes'.format(len(data)))
        session = backend.create_session()
        tx_hash = None
        signed_tx = None
        try:
            tx_hash = adapter.add(data_hex, chain_spec, session=session)
        except ValueError as e:
            try:
                signed_tx = adapter.get(data_hex, chain_spec, session=session) 
            except ValueError as e:
                logg.error('invalid input: {}'.format(e))

        if tx_hash != None:
            session.commit()
            try:
                r = int(0).to_bytes(4, byteorder='big')
                r += strip_0x(tx_hash).encode('utf-8')
                srvs.send(r)
                logg.debug('{} bytes sent'.format(r))
            except BrokenPipeError:
                logg.debug('they just hung up. how rude.')
        elif signed_tx != None:
            r = int(0).to_bytes(4, byteorder='big')
            r += strip_0x(signed_tx).encode('utf-8')
            try:
                r = srvs.send(r)
            except BrokenPipeError:
                logg.debug('they just hung up. how useless.')
        else:
            r = srvs.send(int(1).to_bytes(4, byteorder='big'))

        session.close()
        srvs.close()

    ctrl.shutdown(None, None)

if __name__ == '__main__':
    main()
