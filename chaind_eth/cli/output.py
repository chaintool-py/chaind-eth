# standard imports
import logging
import socket
import enum

logg = logging.getLogger(__name__)


class OpMode(enum.Enum):
    STDOUT = 'standard_output'
    UNIX = 'unix_socket'

class Outputter:

    def __init__(self, mode):
        self.out = getattr(self, 'do_' + mode.value)


    def do(self, hx, *args, **kwargs):
        return self.out(hx, *args, **kwargs)


    def do_standard_output(self, hx, *args, **kwargs):
        return hx


    def do_unix_socket(self, hx, *args, **kwargs):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(kwargs['socket'])
        s.send(hx.encode('utf-8'))
        r = s.recv(64+4)
        logg.debug('r {}'.format(r))
        s.close()
        return r[4:].decode('utf-8')
