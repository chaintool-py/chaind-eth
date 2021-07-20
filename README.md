# chaind-eth development tester recipe

chaind-eth is a socket server that acts as a automated transaction handler for an EVM network.

It capabilities are (unchecked box means feature not yet completed):

- [x] unix socket server to accept raw, signed RLP evm transactions
- [x] stateful queueing system following full local and remote lifecycle of the transaction
- [x] transaction dispatcher unit
- [ ] transaction retry unit (for errored or suspended transactions)
- [x] blockchain listener that updates state of transactions in queue
- [x] CLI transaction listing tool, filterable by:
	* [x] transaction range with lower and/or upper bound
	* [x] only show transaction with errors
	* [x] only show transaction that have not yet completed
- [x] systemd unit / socket service

## prerequisites

For these examples you need:

- python 3.9.x
- pip
- virtualenv
- socat
- sqlite
- an EVM RPC endpoint

For any python command / executable use:

* `-v` or `-vv` to get more information about what is going on
* `--help` for information on how to use and parameters that can be passed


## usage example


### set up database

In terminal window A

Currently there is no more practical way of setting up the database backend :/

```
git clone https://gitlab.com/chaintool/chaind
cd chaind
python -m venv .venv
. .venv/bin/activate
pip install --extra-index-url https://pip.grassrootseconomics.net:8433 -r requirements.txt
# the following will set up your database in ~/.local/share/chaind/eth/chaind.sqlite
PYTHONPATH=. CHAIND_DOMAIN=eth DATABASE_ENGINE=sqlite python scripts/migrate.py
```

### create an empty working directory

```
d=$(mktemp -d) && cd $d
```

### create a chaind-eth sandbox

```
python -m venv .venv
. .venv/bin/activate
pip install --extra-index-url https://pip.grassrootseconomics.net:8433 "chaind-eth>=0.0.1a2"
```

### start the services

In terminal window B

```
cd <working directory>
. .venv/bin/activate
export DATABASE_ENGINE=sqlite
export RPC_HTTP_PROVIDER=<your_provider>
export CHAIN_SPEC=<chain_spec_of_provider>
chaind-eth-server --session-id testsession
```

In terminal window C

```
cd <working directory>
. .venv/bin/activate
export DATABASE_ENGINE=sqlite
export RPC_HTTP_PROVIDER=<your_provider>
export CHAIN_SPEC=<chain_spec_of_provider>
chaind-eth-syncer
```

### prepare test transactions

Create two transactions from sender in keyfile (which needs to have gas balance) to a newly created account

```
export WALLET_KEY_FILE=<path_to_keyfile>
export WALLET_PASSWORD=<keyfile_password_if_needed>
export RPC_HTTP_PROVIDER=<your_provider>
export CHAIN_SPEC=<chain_spec_of_provider>

# create new account and store address in variable
eth-keyfile -z > testkey.json
recipient=$(eth-keyfile -z -d testkey.json)

# create transactions
eth-gas --raw -a $recipient 1024 > tx1.txt
eth-gas --raw -a $recipient 2048 > tx2.txt
eth-gas --raw -a $recipient 4096 > tx3.txt
```

### send test transactions to queue

```
cat tx1.txt | socat UNIX-CLIENT=/run/user/$UID/testsession/chaind.sock
cat tx2.txt | socat UNIX-CLIENT=/run/user/$UID/testsession/chaind.sock
cat tx3.txt | socat UNIX-CLIENT=/run/user/$UID/testsession/chaind.sock
```

### check status of transactions

```
export DATABASE_ENGINE=sqlite
sender=$(eth-keyfile -d $WALLET_KEY_FILE)
DATABASE_NAME=$HOME/.local/share/chaind/eth/chaind.sqlite chainqueue-list $sender
# to show a summary only instead all transactions
DATABASE_NAME=$HOME/.local/share/chaind/eth/chaind.sqlite chainqueue-list --summary $sender
```

The `chainqueue-list` tool provides some basic filtering. Use `chainqueue-list --help` to see what they are.


## systemd

TBC
