# Votemarket Proofs Script

⚙️ Streamlined toolkit for generating Votemarket V2 proofs and interacting with the protocol

## Overview

This toolkit provides a set of utilities for interacting with Votemarket V2, specifically designed for generating proofs from Ethereum and facilitating claim operations. It's an essential tool for cross-chain voting mechanisms and proof generation in the Votemarket ecosystem.

## Features

- Generate user proofs for Votemarket V2
- Generate gauge proofs for Votemarket V2
- Retrieve block information
- Interact with Votemarket V2 for claiming operations
- Support for multiple protocols (Curve, Balancer, Frax, FXN)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/stake-dao/votemarket-proofs-script.git
   cd votemarket-proofs-script
   ```

2. Set up a virtual environment and install dependencies:
   ```
   make install
   ```

## Usage

The toolkit provides several ways to generate proofs and interact with Votemarket V2:

### Using the Makefile

Generate user proof:

```
make user-proof RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID PROTOCOL=curve GAUGE_ADDRESS=0x... USER=0x... BLOCK_NUMBER=12345678
```


Generate gauge proof:

```
make gauge-proof RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID PROTOCOL=curve GAUGE_ADDRESS=0x... CURRENT_PERIOD=1234567890 BLOCK_NUMBER=12345678
```

Get block information:

```
make block-info RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID BLOCK_NUMBER=12345678
```


### Using in a flow via scripts
You can also use scripts directly for integration or chained actions. See the example script for basic usage:

``` python:script/examples/generate_proof_example.py ```


## Configuration

The toolkit supports protocols that have a gauge controller and are integrated with the Votemarket V2 platform. You can see integrated ones on :
```shared/constants```


## TODO :
Package and example script checking all deployed VMs using Stake DAO address book + voters for active bounties + encoding all