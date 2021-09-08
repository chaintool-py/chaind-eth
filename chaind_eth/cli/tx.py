# standard imports
import logging

logg = logging.getLogger(__name__)

class TxProcessor:

    def load(self, s):
        contents = []
        f = None
        try:
            f = open(s, 'r')
        except FileNotFoundError:
            return None

        contents = f.readlines()
        f.close()
        for i in range(len(contents)):
            contents[i] = contents[i].rstrip()
        return contents

    def __str__(self):
        return 'tx processor'
