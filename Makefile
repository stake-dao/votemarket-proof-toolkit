# Makefile for VoteMarket Proofs Generation

# Configuration
PYTHON := python3
VENV := venv
VENV_ACTIVATE := . $(VENV)/bin/activate
SRC_DIR := script

# Phony targets declaration
.PHONY: all install clean user-proof gauge-proof block-info test help integration

# Default target: Set up the virtual environment and install dependencies
all: install

# Create virtual environment and install dependencies
install: $(VENV)/bin/activate
$(VENV)/bin/activate: requirements.txt
	PYTHONPATH=script $(PYTHON) -m venv $(VENV)
	$(VENV_ACTIVATE) && pip install -r requirements.txt

# Remove virtual environment and cached Python files
clean:
	rm -rf $(VENV)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete

# Generate user proof for VoteMarketV2
# Required variables:
# - PROTOCOL: Protocol name (e.g., 'curve')
# - GAUGE_ADDRESS: Ethereum address of the gauge
# - USER: Ethereum address of the user
# - BLOCK_NUMBER: Ethereum block number for the proof
user-proof: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.main import VoteMarketProofs; \
		vm = VoteMarketProofs(1); \
		user_proof = vm.get_user_proof('$(PROTOCOL)', '$(GAUGE_ADDRESS)', '$(USER)', $(BLOCK_NUMBER)); \
		print('User Proof:'); \
		print(f'0x{user_proof[\"storage_proof\"].hex()}')"

# Generate gauge proof for VoteMarketV2
# Required variables:
# - PROTOCOL: Protocol name (e.g., 'curve')
# - GAUGE_ADDRESS: Ethereum address of the gauge
# - CURRENT_EPOCH: Current voting epoch
# - BLOCK_NUMBER: Ethereum block number for the proof
gauge-proof: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.main import VoteMarketProofs; \
		vm = VoteMarketProofs(1); \
		gauge_proof = vm.get_gauge_proof('$(PROTOCOL)', '$(GAUGE_ADDRESS)', $(CURRENT_EPOCH), $(BLOCK_NUMBER)); \
		print('Gauge Proof:'); \
		print(f'  Proof for block (Gauge controller) : 0x{gauge_proof[\"gauge_controller_proof\"].hex()}'); \
		print(f'  Proof for point (Gauge data): 0x{gauge_proof[\"point_data_proof\"].hex()}')"

# Get block information for VoteMarketV2
# Required variables:
# - BLOCK_NUMBER: Ethereum block number to retrieve information for
block-info: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.main import VoteMarketProofs; \
		vm = VoteMarketProofs(1); \
		info = vm.get_block_info($(BLOCK_NUMBER)); \
		print('Block Info:'); \
		print(f'  Block Number: {info[\"block_number\"]}'); \
		print(f'  Block Hash: {info[\"block_hash\"]}'); \
		print(f'  Block Timestamp: {info[\"block_timestamp\"]}'); \
		print(f'  RLP Block Header (used for setBlockData): {info[\"rlp_block_header\"]}')"


# Get active campaigns for a given chain + platform
# Required variables:
# - CHAIN_ID: Chain ID (e.g., 1 for Ethereum Mainnet)
# - PLATFORM: Platform address (e.g., '0x...')
get-active-campaigns: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from votes.main import VoteMarketVotes; \
		vm = VoteMarketVotes($(CHAIN_ID)); \
		campaigns = vm.get_active_campaigns($(CHAIN_ID), '$(PLATFORM)'); \
		print('Active Campaigns:'); \
		[print(f'  Campaign ID: {campaign[\"id\"]}, Gauge: {campaign[\"gauge\"]}, Listed Users: {campaign[\"listed_users\"]}') for campaign in campaigns]"

# Run tests
test: install
	$(VENV_ACTIVATE) && ape test --network arbitrum:mainnet-fork

# Display help information
help:
	@echo "VoteMarket Proofs Generator Makefile"
	@echo ""
	@echo "This Makefile facilitates the generation of RLP-encoded proofs for VoteMarketV2."
	@echo "It includes targets for generating user proofs, gauge proofs, and block information."
	@echo ""
	@echo "Available targets:"
	@echo "  all         : Set up the virtual environment and install dependencies"
	@echo "  install     : Same as 'all'"
	@echo "  clean       : Remove virtual environment and cached Python files"
	@echo "  user-proof  : Generate a user proof (requires PROTOCOL, GAUGE_ADDRESS, USER, BLOCK_NUMBER)"
	@echo "  gauge-proof : Generate a gauge proof (requires PROTOCOL, GAUGE_ADDRESS, CURRENT_EPOCH, BLOCK_NUMBER)"
	@echo "  block-info  : Get block information (requires BLOCK_NUMBER)"
	@echo "  help        : Display this help message"
	@echo ""
	@echo "Example usage:"
	@echo "  make user-proof PROTOCOL=curve GAUGE_ADDRESS=0x... USER=0x... BLOCK_NUMBER=12345678"

integration:
	$(VENV_ACTIVATE) && make -f script/tests/integration/Makefile $(TARGET)