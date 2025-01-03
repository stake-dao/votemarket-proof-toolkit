<div align="center">
<img src="./assets/Inspector.svg" width="200">

# VotemarketV2 Proofs Toolkit

⚙️ Streamlined toolkit for generating Votemarket V2 proofs and interacting with the protocol

[![GitHub issues](https://img.shields.io/github/issues/stake-dao/votemarket-proof-toolkit.svg)](https://github.com/stake-dao/votemarket-proof-toolkit/issues)
[![GitHub stars](https://img.shields.io/github/stars/stake-dao/votemarket-proof-generator.svg)](https://github.com/stake-dao/votemarket-proof-toolkit/stargazers)

</div>

## Table of Contents

- [VotemarketV2 Proofs Toolkit](#votemarketv2-proofs-toolkit)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Features](#features)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Usage](#usage)
    - [Using the Makefile](#using-the-makefile)
    - [Using Python Scripts](#using-python-scripts)
  - [Understanding Block Numbers and Proofs](#understanding-block-numbers-and-proofs)
  - [Documentation](#documentation)

## Introduction

The VotemarketV2 Proofs Toolkit is a set of utilities designed to interact with Votemarket V2, focusing on generating Ethereum proofs for claim operations. This toolkit streamlines the process of creating proofs, making it easier for developers and users to interact with the VM Oracle.

## Features

- Generate user proofs
- Generate gauge proofs
- Retrieve block information
- Support for multiple protocols (Curve, Balancer, Frax, FXN)
- Get voters for a gauge
- Get active campaigns on Votemarket

## Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
  ```bash
  # Install uv
  pip install uv
  # or
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/stake-dao/votemarket-proof-toolkit.git
   cd votemarket-proof-toolkit
   ```

2. **Install dependencies using uv:**
   ```bash
   make install-dev
   ```

3. **Verify installation:**
   ```bash
   make help
   ```

## Quick Start

1. **View available commands:**
   ```bash
   make help
   ```

2. **Generate a user proof:**
   ```bash
   make user-proof PROTOCOL=curve GAUGE_ADDRESS=0x... USER_ADDRESS=0x... BLOCK_NUMBER=12345678
   ```

3. **Run example scripts:**
   ```bash
   make run-examples
   ```

## Configuration

1. Create a `.env` file in the root directory of the project.
2. Add your RPC URLs to the `.env` file:
   ```
   ETHEREUM_MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/API_KEY

   ARBITRUM_MAINNET_RPC_URL=https://arb-mainnet.g.alchemy.com/v2/API_KEY

   ... (depending on where VM are deployed)

   ```

## Usage

The toolkit provides multiple ways to generate proofs for interacting with Votemarket V2:

### Using the Makefile

1. **Generate user proof:**
   ```bash
   make user-proof PROTOCOL=curve GAUGE_ADDRESS=0x... USER=0x... BLOCK_NUMBER=12345678
   ```

2. **Generate gauge proof:**
   ```bash
   make gauge-proof PROTOCOL=curve GAUGE_ADDRESS=0x... CURRENT_EPOCH=1234567890 BLOCK_NUMBER=12345678
   ```

3. **Get block information:**
   ```bash
   make block-info BLOCK_NUMBER=12345678
   ```

### Using Python Scripts

You can also use the Python scripts directly for more complex integrations or chained actions. Refer to the `examples` and `external` directories for sample usage. `external` is used for the API and Stake Dao weekly operations.****

## Understanding Block Numbers and Proofs

The `BLOCK_NUMBER` parameter is crucial when generating proofs. This number should be the block set in the Votemarket oracle for the specific period you're interested in claiming (period is rounded down by week, as on mainnet gauge controller).

To get the correct block number for a specific epoch or set of epochs, you can use the following Makefile command:

```bash
make get-epoch-blocks CHAIN_ID=1 PLATFORM=0x... EPOCHS=1234,1235,1236
```

This command will return the block numbers set in the oracle for the specified epochs. For example:

```
Epoch Blocks:
  Epoch 1234: Block 15000000
  Epoch 1235: Block 15007000
  Epoch 1236: Block 15014000
```

Use these block numbers when generating proofs to ensure they match the oracle's state for the relevant epoch.

## Documentation

For detailed information on each component and function, please refer to:

- [Developer Documentation](docs/README.md): Comprehensive guide for integrating with VoteMarket V2, including:
  - Contract addresses and deployments
  - Campaign creation and management
  - Claiming rewards
  - Using the Bundler for batch operations

The developer documentation provides detailed examples and best practices for integrating with the protocol, while the source code documentation offers technical details about implementation.

## Usage

See `make help` for available commands or run specific examples:

```bash
# Show all available commands
make help

# Run specific example
make run-example EXAMPLE=create_campaign_l1
```

For detailed implementation examples, check the `docs/examples/` directory.
