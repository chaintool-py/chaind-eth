# chaind-eth development tester recipe

chaind-eth is a socket server that acts as a automated transaction handler for an EVM network.

It capabilities are (unchecked box means feature not yet completed):

- [x] unix socket server to accept raw, signed RLP evm transactions
- [x] stateful queueing system following full local and remote lifecycle of the transaction
- [x] transaction dispatcher unit
- [x] transaction retry unit (for errored or suspended transactions)
- [x] blockchain listener that updates state of transactions in queue
- [x] CLI transaction listing tool, filterable by:
	* [x] transaction range with lower and/or upper bound
	* [x] only show transaction with errors
	* [x] only show transaction that have not yet completed
- [x] systemd unit / socket service
- [x] sql storage backend
- [x] filesystem storage backend


## prerequisites

For these examples you need:

- linux (tested on 5.12.x, perhaps wsl/macos will work too, no guarantees, though)
- python 3.9.x
- pip
- virtualenv
- socat
- sqlite
- an EVM RPC endpoint

For any python command / executable used below:

* add `-v` or `-vv` to get more information about what is going on
* use with `--help` for information on how to use and parameters that can be passed


## setting up the database backend

Currently there is no more practical way of setting up the database backend than to pull the repository and run a database migration script :/

```
git clone https://git.defalsify.org/chaind
cd chaind
python -m venv .venv
. .venv/bin/activate
pip install --extra-index-url https://pip.grassrootseconomics.net -r requirements.txt
# the following will set up your database in ~/.local/share/chaind/eth/chaind.sqlite
PYTHONPATH=. CHAIND_DOMAIN=eth DATABASE_ENGINE=sqlite python scripts/migrate.py
```


## usage example

### create an empty working directory

In terminal window A

```
d=$(mktemp -d) && cd $d
```

### create a chaind-eth sandbox

```
python -m venv .venv
. .venv/bin/activate
pip install --extra-index-url https://pip.grassrootseconomics.net "chaind-eth>=0.0.3a5"
```

### start the services

In terminal window B

```
cd <working directory>
. .venv/bin/activate
export DATABASE_ENGINE=sqlite
export RPC_PROVIDER=<your_provider>
export CHAIN_SPEC=<chain_spec_of_provider>
chaind-eth-server --session-id testsession
```

In terminal window C

```
cd <working directory>
. .venv/bin/activate
export DATABASE_ENGINE=sqlite
export RPC_PROVIDER=<your_provider>
export CHAIN_SPEC=<chain_spec_of_provider>
chaind-eth-syncer
```

### prepare test transactions

Create two transactions from sender in keyfile (which needs to have gas balance) to a newly created account

```
export WALLET_KEY_FILE=<path_to_keyfile>
export WALLET_PASSWORD=<keyfile_password_if_needed>
export RPC_PROVIDER=<your_provider>
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
cat tx1.txt | socat UNIX-CLIENT:/run/user/$UID/chaind/eth/testsession/chaind.sock -
cat tx2.txt | socat UNIX-CLIENT:/run/user/$UID/chaind/eth/testsession/chaind.sock -
cat tx3.txt | socat UNIX-CLIENT:/run/user/$UID/chaind/eth/testsession/chaind.sock -
```

### check status of transactions


`chainqueue-list` outputs details about transactions in the queue.

Provided the initial database migration was executed as described above, the execution would look as follows:

```
export DATABASE_ENGINE=sqlite
export DATABASE_NAME=$HOME/.local/share/chaind/eth/chaind.sqlite 
export CHAIN_SPEC=<chain_spec_of_provider>
sender=$(eth-keyfile -d $WALLET_KEY_FILE)
chainqueue-list $sender
```

To show a summary only instead all transactions:

```
chainqueue-list --summary $sender
```

The `chaind-list` tool can be used to list by session id. Following the above examples:

```
export DATABASE_ENGINE=sqlite
export CHAIN_SPEC=<chain_spec_of_provider>
chaind-list testsession
```

The `chainqueue-list` and `chaind-list` tools both provides the same basic filtering. Use `--help` to see the details.


### Retrieve transaction by hash

The socket server returns the transaction hash when a transaction is submitted.

If a socket server is given a transaction hash, it will return the transaction data for that hash (if it exists).

Extending the previous examples, this will output the original signed transaction:

```
eth-gas --raw -a $recipient 1024 > tx1.txt
cat tx1.txt | socat UNIX-CLIENT:/run/user/$UID/chaind/eth/testsession/chaind.sock - | cut -b 4- > hash1.txt 
cat hash1.tx | socat UNIX-CLIENT:/run/user/$UID/chaind/eth/testsession/chaind.sock - | cut -b 4- > tx1_recovered.txt
diff tx1_recovered.txt tx1.txt
# should output 0
echo $?
```

The first 4 bytes of the data returned from the socket is a 32-bit big-endian result code. The data payload follows from the 5th byte.


## Batch processing

The `chaind-eth-send` executable generates signed transactions with data from a csv file.

The data columns must be in the following order:

1. receipient address
2. transaction value
3. token specifier (optional, network fee token if not given)
4. network fee token value (optional)


If the gas token value (4) is not given for a gas token transaction, the transaction value (2) will be used.

By default the signed transactions are output as hex to stdout, each on a separate line.

If a valid `--socket` is given (i.e. the socket of the `chaind-eth-server`) the transactions will be send to the socket instead. The hash of the transaction will be output to standard output.


### Using token symbols

If token symols are to be used in some or all values of column 3, then a valid `--token-index` executable address is required (in this case, a smart contract implementing the [`registry`](https://gitlab.com/cicnet/eth-contract-registry/-/blob/master/solidity/Registry.sol) contract interface).


### Input validity checks

The validity of the input data is verified _before_ actual execution takes place.

These checks include:

- The token can be made sense of.
- The values can be parsed to integer amounts.
- The recipient address is a valid checksum address.

The checks do however _not_ include whether the token balances of the signer are sufficient to successfully execute the transactions on the network.


### CSV input example

```
0x72B70906fD07c72f2d96aAA250C2D31662D0d809,10,0xb708175e3f6Cd850643aAF7B32212AFad50e2549
0xD536CB6d1d9B8d33875E0ba0Aa3515eD7478f889,0x2a,GFT,100
0xeE08b59a95E822AE346489038D25750C8EdfcC25,0x029a
```

This will result in the following transactions:

1. send 10 tokens from token contract `0xb708175e3f6Cd850643aAF7B32212AFad50e2549` to recipient `0x72B70906fD07c72f2d96aAA250C2D31662D0d809`.
2. send 42 `GFT` tokens along with 100 network gas tokens to recipient `0xD536CB6d1d9B8d33875E0ba0Aa3515eD7478f889`
3. send 666 network gas tokens to recipient `0xeE08b59a95E822AE346489038D25750C8EdfcC25`


### Resending transactions

Since the `chaind-eth-server` does not have access to signing keys, resending stalled transactions is also a separate external action.

The `chaind-eth-resend` executable takes a list of signed transactions (e.g. as output from `chaind-eth-send` using the socket) and automatically increases the fee price of the transaction to create a replacement.

As with `chaind-eth-send`, the resend executable optionally takes a socket argument that sends the transaction directly to a socket. Otherwise, the signed transactions are send to standard output.

For example, the following will output details of the transaction generated by `chaind-eth-resend`, in which the fee price has been slightly incremented:

```
eth-gas --raw --fee-price 100000000 -a $recipient 1024 > tx1.txt
chaind-eth-resend tx1.txt > tx1_bump.txt
cat tx1_bump.txt | eth-decode
```


### Retrieving transactions for resend

The `chaind-list` tool can be used to retrieve transactions with the same filters as `chainqueue-list`, but also allowing results limited a specific session id.

As with `chainqueue-list`, which column to output can be customized. This enables creation of signed transaction lists in the format accepted by `chaind-eth-resent`.

One examples of criteria for transactions due to be resent may be:

```
# get any pending transaction in session "testsession"
export DATABASE_ENGINE=sqlite
chaind-list -o signedtx --pending testsession
```

Note that the `chaind-list` tool requires a connection to the queueing backend.


## systemd

TBC
