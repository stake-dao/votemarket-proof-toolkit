# Makefile for VoteMarket Proofs Generation

# Configuration
PYTHON := python3
VENV := venv
VENV_ACTIVATE := . $(VENV)/bin/activate
SRC_DIR := script

# Phony targets declaration
.PHONY: all install clean test help integration
.PHONY: user-proof gauge-proof block-info get-active-campaigns get-epoch-blocks

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

# Run integration tests
integration:
	$(VENV_ACTIVATE) && make -f script/tests/integration/Makefile $(TARGET)

# Proof generation commands
user-proof: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.main import VoteMarketProofs; \
		vm = VoteMarketProofs(1); \
		user_proof = vm.get_user_proof('$(PROTOCOL)', '$(GAUGE_ADDRESS)', '$(USER)', $(BLOCK_NUMBER)); \
		print('User Proof:'); \
		print(f'0x{user_proof[\"storage_proof\"].hex()}')"

gauge-proof: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.main import VoteMarketProofs; \
		vm = VoteMarketProofs(1); \
		gauge_proof = vm.get_gauge_proof('$(PROTOCOL)', '$(GAUGE_ADDRESS)', $(CURRENT_EPOCH), $(BLOCK_NUMBER)); \
		print('Gauge Proof:'); \
		print(f'  Proof for block (Gauge controller) : 0x{gauge_proof[\"gauge_controller_proof\"].hex()}'); \
		print(f'  Proof for point (Gauge data): 0x{gauge_proof[\"point_data_proof\"].hex()}')"

# Information retrieval commands
block-info: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from proofs.main import VoteMarketProofs; \
		vm = VoteMarketProofs(1); \
		info = vm.get_block_info($(BLOCK_NUMBER)); \
		print('Block Info:'); \
		print(f'  Block Number: {info[\"block_number\"]}'); \
		print(f'  Block Hash: {info[\"block_hash\"]}'); \
		print(f'  Block Timestamp: {info[\"block_timestamp\"]}'); \
		print(f'  RLP Block Header (used for setBlockData): {info[\"rlp_block_header\"]}')"

get-active-campaigns: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from data.main import VoteMarketData; \
		vm = VoteMarketData($(CHAIN_ID)); \
		campaigns = vm.get_active_campaigns($(CHAIN_ID), '$(PLATFORM)'); \
		print('Active Campaigns:'); \
		[print(f'  Campaign ID: {campaign[\"id\"]}, Gauge: {campaign[\"gauge\"]}, Listed Users: {campaign[\"listed_users\"]}') for campaign in campaigns]"

get-epoch-blocks: install
	$(VENV_ACTIVATE) && $(PYTHON) -c "from data.main import VoteMarketData; \
		vm = VoteMarketData($(CHAIN_ID)); \
		epochs = [int(e) for e in '$(EPOCHS)'.split(',')]; \
		blocks = vm.get_epochs_block($(CHAIN_ID), '$(PLATFORM)', epochs); \
		print('Epoch Blocks:'); \
		[print(f'  Epoch {epoch}: Block {block}') for epoch, block in blocks.items()]"

# Display help information
help:
	@echo "VoteMarket Proofs Generator Makefile"
	@echo ""
	@echo "This Makefile facilitates the generation of RLP-encoded proofs for VoteMarketV2."
	@echo "It includes targets for generating user proofs, gauge proofs, and retrieving various information."
	@echo ""
	@echo "Available targets:"
	@echo "  all                : Set up the virtual environment and install dependencies"
	@echo "  install            : Same as 'all'"
	@echo "  clean              : Remove virtual environment and cached Python files"
	@echo "  test               : Run tests"
	@echo "  integration        : Run integration tests"
	@echo "  user-proof         : Generate a user proof (requires PROTOCOL, GAUGE_ADDRESS, USER, BLOCK_NUMBER)"
	@echo "  gauge-proof        : Generate a gauge proof (requires PROTOCOL, GAUGE_ADDRESS, CURRENT_EPOCH, BLOCK_NUMBER)"
	@echo "  block-info         : Get block information (requires BLOCK_NUMBER)"
	@echo "  get-active-campaigns: Get active campaigns for a given chain and platform (requires CHAIN_ID, PLATFORM)"
	@echo "  get-epoch-blocks   : Get set blocks for a list of epochs (requires CHAIN_ID, PLATFORM, EPOCHS)"
	@echo "  help               : Display this help message"
	@echo ""
	@echo "Example usage:"
	@echo "  make user-proof PROTOCOL=curve GAUGE_ADDRESS=0x... USER=0x... BLOCK_NUMBER=12345678"
	@echo "  make get-epoch-blocks CHAIN_ID=1 PLATFORM=0x... EPOCHS=1234,1235,1236"
