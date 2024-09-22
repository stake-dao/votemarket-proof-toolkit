# Makefile for VM Proofs

# Python interpreter
PYTHON := python3

# Virtual environment
VENV := venv
VENV_ACTIVATE := . $(VENV)/bin/activate

# Source directories
SRC_DIR := script

# Default target
.PHONY: all
all: install

# Create virtual environment and install dependencies
.PHONY: install
install: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV_ACTIVATE) && pip install -r requirements.txt

# Clean up
.PHONY: clean
clean:
	rm -rf $(VENV)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete

# Generate user proof
.PHONY: user-proof
user-proof: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.VMProofs import VoteMarketProofs; \
		vm = VoteMarketProofs('$(RPC_URL)'); \
		account_proof, storage_proof = vm.get_user_proof('$(PROTOCOL)', '$(GAUGE_ADDRESS)', '$(USER)', $(BLOCK_NUMBER)); \
		print(f'Account Proof: {account_proof.hex()}'); \
		print(f'Storage Proof: {storage_proof.hex()}')"

# Generate gauge proof
.PHONY: gauge-proof
gauge-proof: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.VMProofs import VoteMarketProofs; \
		vm = VoteMarketProofs('$(RPC_URL)'); \
		account_proof, storage_proof = vm.get_gauge_proof('$(PROTOCOL)', '$(GAUGE_ADDRESS)', $(CURRENT_PERIOD), $(BLOCK_NUMBER)); \
		print(f'Account Proof: {account_proof.hex()}'); \
		print(f'Storage Proof: {storage_proof.hex()}')"

# Get block info
.PHONY: block-info
block-info: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.VMProofs import VoteMarketProofs; \
		vm = VoteMarketProofs('$(RPC_URL)'); \
		info = vm.get_block_info($(BLOCK_NUMBER)); \
		print(f\"Block Number: {info['BlockNumber']}\"); \
		print(f\"Block Hash: {info['BlockHash']}\"); \
		print(f\"Block Timestamp: {info['BlockTimestamp']}\"); \
		print(f\"RLP Block Header: {info['RlpBlockHeader']}\")"

# Help target
.PHONY: help
help:
	@echo "VoteMarket Proofs Generator Makefile"
	@echo ""
	@echo "This Makefile is designed to facilitate the generation of RLP-encoded proofs"
	@echo "for VoteMarketV2. It includes targets for generating user proofs,"
	@echo "gauge proofs, and block information"
	@echo ""
	@echo "Available targets:"
	@echo "  all         : Set up the virtual environment and install dependencies"
	@echo "  install     : Same as 'all'"
	@echo "  clean       : Remove virtual environment and cached Python files"
	@echo "  user-proof  : Generate a user proof (requires RPC_URL, PROTOCOL, GAUGE_ADDRESS, USER, BLOCK_NUMBER)"
	@echo "  gauge-proof : Generate a gauge proof (requires RPC_URL, PROTOCOL, GAUGE_ADDRESS, CURRENT_PERIOD, BLOCK_NUMBER)"
	@echo "  block-info  : Get block information (requires RPC_URL, BLOCK_NUMBER)"
	@echo "  help        : Display this help message"
	@echo ""
	@echo "Example usage:"
	@echo "  make user-proof RPC_URL=https://mainnet.infura.io/v3/YOUR-PROJECT-ID PROTOCOL=curve GAUGE_ADDRESS=0x... USER=0x... BLOCK_NUMBER=12345678"