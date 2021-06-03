# standard imports
import syslog
import sys
import time
import socket
import signal
import os
import logging
import stat
import argparse
import uuid

# external imports
import confini
from xdg.BaseDirectory import (
        xdg_data_dirs,
        get_runtime_dir,
        load_first_config,
        )
from hexathon import strip_0x
from chainlib.chain import ChainSpec
from chainlib.eth.connection import EthHTTPConnection
from chainqueue.sql.backend import SQLBackend
from chainqueue.db import dsn_from_config

# local imports
from chainqueue.adapters.eth import EthAdapter

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

default_config_dir = load_first_config('chainqueue')
config_dir = os.environ.get('CONFINI_DIR', default_config_dir)

default_runtime_dir = os.path.join(get_runtime_dir(), 'chainqueue')
default_data_dir = os.path.join(xdg_data_dirs[0], 'chainqueue')

argparser = argparse.ArgumentParser('chainqueue transaction submission and trigger server')
argparser.add_argument('-c', '--config', dest='c', type=str, default=config_dir, help='configuration directory')
argparser.add_argument('-p', type=str, help='rpc endpoint')
argparser.add_argument('-i', type=str, help='chain spec')
argparser.add_argument('--runtime-dir', dest='runtime_dir', type=str, default=default_runtime_dir, help='runtime directory')
argparser.add_argument('--data-dir', dest='data_dir', type=str, default=default_data_dir, help='data directory')
argparser.add_argument('--session-id', dest='session_id', type=str, default=str(uuid.uuid4()), help='session id to use for session')
argparser.add_argument('-v', action='store_true', help='be verbose')
argparser.add_argument('-vv', action='store_true', help='be very verbose')
args = argparser.parse_args(sys.argv[1:])

if args.vv:
    logg.setLevel(logging.DEBUG)
elif args.v:
    logg.setLevel(logging.INFO)

# process config
config = confini.Config(args.c)
config.process()
args_override = {
            'SESSION_RUNTIME_DIR': getattr(args, 'runtime_dir'),
            'SESSION_CHAIN_SPEC': getattr(args, 'i'),
            'RPC_ENDPOINT': getattr(args, 'p'),
            'PATH_DATA': getattr(args, 'data_dir'),
        }
config.dict_override(args_override, 'cli args')
config.add(getattr(args, 'session_id'), '_SESSION_ID', True)

if not config.get('SESSION_SOCKET_PATH'):
    socket_path = os.path.join(config.get('SESSION_RUNTIME_DIR'), config.get('_SESSION_ID'), 'chainqueue.sock')
    config.add(socket_path, 'SESSION_SOCKET_PATH', True)

if config.get('DATABASE_ENGINE') == 'sqlite':
    config.add(os.path.join(config.get('PATH_DATA'), config.get('DATABASE_NAME')), 'DATABASE_NAME', True)
    

logg.debug('config loaded:\n{}'.format(config))


# verify setup
try:
    os.stat(config.get('DATABASE_NAME'))
except FileNotFoundError:
    sys.stderr.write('database file {} not found. please run database migration script first'.format(config.get('DATABASE_NAME')))
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
        self.srv.settimeout(4.0)

    def shutdown(self, signo, frame):
        if self.dead:
            return
        self.dead = True
        if signo != None:
            syslog.syslog('closing on {}'.format(signo))
        else:
            syslog.syslog('explicit shutdown')
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

chain_spec = ChainSpec.from_chain_str(config.get('SESSION_CHAIN_SPEC'))

dsn = dsn_from_config(config)
backend = SQLBackend(dsn, debug=config.true('DATABASE_DEBUG'))
adapter = EthAdapter(backend)
rpc = EthHTTPConnection(url=config.get('RPC_ENDPOINT'), chain_spec=chain_spec)

def main():
    havesends = 0
    while True:
        srvs = None
        try:
            logg.debug('getting connection')
            (srvs, srvs_addr) = ctrl.get_connection()
        except OSError as e:
            havesends = 0
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
                txs = adapter.upcoming(chain_spec)
                for k in txs.keys():
                    havesends += 1
                    logg.debug('txs {} {}'.format(k, txs[k]))
                    adapter.dispatch(chain_spec, rpc, k, txs[k])
                if havesends > 0:
                    ctrl.srv.settimeout(0.1)
                else:
                    ctrl.srv.settimeout(4.0)
                continue
        ctrl.srv.settimeout(0.1)
        srvs.settimeout(0.1)
        data_in = None
        try:
            data_in = srvs.recv(1024)
        except BlockingIOError as e:
            logg.debug('block io error: {}'.format(e))
            continue

        data = None
        try:
            data_in_str = data_in.decode('utf-8')
            data = bytes.fromhex(strip_0x(data_in_str))
        except ValueError:
            logg.error('invalid input "{}"'.format(data_in_str))
            continue

        logg.debug('recv {} bytes'.format(len(data)))
        r = adapter.add(chain_spec, data)
        r = srvs.send(r.to_bytes(4, byteorder='big'))
        logg.debug('{} bytes sent'.format(r))
        srvs.close()

    ctrl.shutdown(None, None)

if __name__ == '__main__':
    main()
