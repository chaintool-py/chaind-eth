# standard imports
import os
import logging
import sys
import datetime
import enum
import re
import stat

# external imports
import chainlib.eth.cli
from chaind import Environment

# local imports
from chaind_eth.cli.process import Processor
from chaind_eth.cli.csv import CSVProcessor
from chaind.error import TxSourceError

logging.basicConfig(level=logging.WARNING)
logg = logging.getLogger()

script_dir = os.path.dirname(os.path.realpath(__file__)) 
config_dir = os.path.join(script_dir, '..', 'data', 'config')


arg_flags = chainlib.eth.cli.argflag_std_write
argparser = chainlib.eth.cli.ArgumentParser(arg_flags)
argparser.add_argument('--socket', dest='socket', type=str, help='Socket to send transactions to')
argparser.add_positional('source', required=False, type=str, help='Transaction source file')
args = argparser.parse_args()



extra_args = {
        'socket': None,
        'source': None,
        }

env = Environment(domain='eth', env=os.environ)
config = chainlib.eth.cli.Config.from_args(args, arg_flags, extra_args=extra_args, base_config_dir=config_dir)

class OpMode(enum.Enum):
    STDOUT = 'standard output'
    UNIX = 'unix socket'
mode = OpMode.STDOUT

re_unix = r'^ipc:///.+'
if re.match(re_unix, config.get('_SOCKET', '')):
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
    sys.stderr.write('source data missing')
    sys.exit(1)


def main():
    processor = Processor(config.get('_SOURCE'))
    processor.add_processor(CSVProcessor())
    try:
        r = processor.process()
    except TxSourceError as e:
        sys.stderr.write('source still unknown after trying processors: {}\n'.format(str(processor)))
        sys.exit(1)

if __name__ == '__main__':
    main()
