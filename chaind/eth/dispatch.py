# external imports
from chainlib.eth.tx import raw


class EthDispatcher:

    def __init__(self, conn):
        self.conn = conn


    def send(self, payload):
        o = raw(payload)
        self.conn.do(o)
