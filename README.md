# VotemarketV2 Proofs Script

⚙️ Streamlined toolkit for generating Votemarket V2 proofs and interacting with the protocol

## Overview

This toolkit provides a set of utilities for interacting with Votemarket V2, specifically designed for generating proofs from Ethereum for claim operations. 

## Features

- Generate user proofs
- Generate gauge proofs
- Retrieve block information
- Support for multiple protocols (Curve, Balancer, Frax, FXN)
- Get voters for a gauge
- Get active campaigns on Votemarket

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

The toolkit provides a way to generate proofs for interacting with Votemarket V2:

### Using the Makefile

Generate user proof:

```
make user-proof RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID PROTOCOL=curve GAUGE_ADDRESS=0x... USER=0x... BLOCK_NUMBER=12345678
```


Generate gauge proof:

```
make gauge-proof RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID PROTOCOL=curve GAUGE_ADDRESS=0x... CURRENT_EPOCH=1234567890 BLOCK_NUMBER=12345678
```

Get block information:

```
make block-info RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID BLOCK_NUMBER=12345678
```


### Using in a flow via scripts
You can also use scripts directly for integration or chained actions. See the examples script for basic usage
