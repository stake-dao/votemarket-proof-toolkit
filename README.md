<div align="center">
<img src="./assets/votemarket-logo.png" width="200">

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

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/stake-dao/votemarket-proof-toolkit.git
   cd votemarket-proof-toolkit
   ```

2. **Set up a virtual environment and install dependencies:**
   ```bash
   make install
   ```

## Configuration

1. Create a `.env` file in the root directory of the project.
2. Add your Ethereum node RPC URL to the `.env` file:
   ```
   ETHEREUM_MAINNET_RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID
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

You can also use the Python scripts directly for more complex integrations or chained actions. Refer to the `examples` and `external` directories for sample usage. `external` is used for the API and Stake Dao weekly operations.

## Documentation

For detailed information on each component and function, please refer to the inline documentation in the source code. Key areas to explore include:

- `proofs/main.py`: Main interface for generating proofs
- `votes/main.py`: Functions for querying votes and campaigns
- `shared/`: Utility functions and shared constants

---

<div align="center">
  <strong>Built with ❤️ by the Stake DAO team</strong>
</div>
