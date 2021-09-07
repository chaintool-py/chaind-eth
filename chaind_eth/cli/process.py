# external imports
from chaind.error import TxSourceError


class Processor:

    def __init__(self, source):
        self.source = source
        self.processor = []
        self.content = []


    def add_processor(self, processor):
        self.processor.append(processor)


    def process(self):
        for processor in self.processor:
            r = processor.process(self.source)
        if r != None:
            return r
        raise TxSourceError()
        

    def __str__(self):
        names = []
        for s in self.processor:
            names.append(str(s))
        return ','.join(names)
