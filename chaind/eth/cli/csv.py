# standard imports
import logging

logg = logging.getLogger(__name__)


class CSVProcessor:

    def load(self, s):
        contents = []
        f = None
        try:
            f = open(s, 'r')
        except FileNotFoundError:
            return None

        import csv # only import if needed
        fr = csv.reader(f)

        for r in fr:
            contents.append(r)
        f.close()
        l = len(contents)
        logg.info('successfully parsed source as csv, found {} records'.format(l))
        return contents


    def __str__(self):
        return 'csv processor'
