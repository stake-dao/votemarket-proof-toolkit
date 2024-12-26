# Makefile for VoteMarket Proofs Generation

# Configuration
PYTHON := uv run
VENV := .venv

# Phony targets declaration
.PHONY: all install clean test help integration
.PHONY: user-proof gauge-proof block-info get-active-campaigns get-epoch-blocks
.PHONY: format lint requirements run-examples

# Default target
all: install

# Development setup
install-dev:
	uv pip install -e ".[dev]"

# Format and lint all Python files using black and ruff
format:
	$(eval TARGET := $(if $(FILE),$(FILE),src/))
	uv run black $(TARGET)
	uv run ruff check --fix $(TARGET)
	uv run ruff format $(TARGET)

clean:
	rm -rf $(VENV) .uv *.egg-info
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.ruff_cache' -delete
	find . -type d -name '.pytest_cache' -delete

# Proof generation commands
user-proof: install
	$(PYTHON) src/votemarket_toolkit/commands/user_proof.py \
		"$(PROTOCOL)" \
		"$(GAUGE_ADDRESS)" \
		"$(USER_ADDRESS)" \
		"$(BLOCK_NUMBER)"

gauge-proof: install
	$(PYTHON) src/votemarket_toolkit/commands/gauge_proof.py \
		"$(PROTOCOL)" \
		"$(GAUGE_ADDRESS)" \
		"$(CURRENT_EPOCH)" \
		"$(BLOCK_NUMBER)"

# Information retrieval commands
block-info: install
	$(PYTHON) src/votemarket_toolkit/commands/block_info.py "$(BLOCK_NUMBER)"

get-active-campaigns: install
	$(PYTHON) src/votemarket_toolkit/commands/active_campaigns.py \
		$(if $(CHAIN_ID),"--chain-id=$(CHAIN_ID)") \
		$(if $(PLATFORM),"--platform=$(PLATFORM)") \
		$(if $(PROTOCOL),"--protocol=$(PROTOCOL)")

get-epoch-blocks: install
	$(PYTHON) src/votemarket_toolkit/commands/get_epoch_blocks.py \
		$(if $(CHAIN_ID),"--chain-id=$(CHAIN_ID)") \
		$(if $(PLATFORM),"--platform=$(PLATFORM)") \
		$(if $(EPOCHS),"--epochs=$(EPOCHS)")

index-votes: install
	$(PYTHON) src/votemarket_toolkit/commands/index_votes.py \
		$(if $(PROTOCOL),"--protocol=$(PROTOCOL)") \
		$(if $(GAUGE_ADDRESS),"--gauge-address=$(GAUGE_ADDRESS)")

# Help and examples
help:
	$(PYTHON) src/votemarket_toolkit/commands/help.py

run-example:
	$(PYTHON) src/votemarket_toolkit/commands/help.py $(EXAMPLE)
	$(PYTHON) docs/examples/$(EXAMPLE).py

.PHONY: all install-dev clean help run-example
.PHONY: user-proof gauge-proof block-info get-active-campaigns get-epoch-blocks

simulate:
	$(PYTHON) src/votemarket_toolkit/scripts/estimate_ccip_gas.py \
	--adapter 0xbF0000F5C600B1a84FE08F8d0013002ebC0064fe \
	--laposte 0xF0000058000021003E4754dCA700C766DE7601C2 \
	--to-address 0xADfBFd06633eB92fc9b58b3152Fe92B0A24eB1FF \
	--tokens 0x41D5D79431A913C4aE7d69a668ecdfE5fF9DFB68 0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F 0x090185f2135308BaD17527004364eBcC2D37e5F6 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 0x30D20208d987713f46DFD34EF128Bb16C404D10f \

# Node/TypeScript commands
install-ts:
	npm install

simulate-ts:
	npx ts-node src/scripts/estimate-ccip-gas.ts \
	--adapter="0xbF0000F5C600B1a84FE08F8d0013002ebC0064fe" \
	--laposte="0xF0000058000021003E4754dCA700C766DE7601C2" \
	--to-address="0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5" \
	--tokens 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 0x090185f2135308BaD17527004364eBcC2D37e5F6 0x41d5d79431a913c4ae7d69a668ecdfe5ff9dfb68 0x30d20208d987713f46dfd34ef128bb16c404d10f

.PHONY: install-ts simulate-ts
