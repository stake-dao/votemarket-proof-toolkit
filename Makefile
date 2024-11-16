# Makefile for VoteMarket Proofs Generation

# Configuration
PYTHON := uv run
VENV := .venv

# Phony targets declaration
.PHONY: all install clean test help integration
.PHONY: user-proof gauge-proof block-info get-active-campaigns get-epoch-blocks
.PHONY: format lint requirements

# Default target: Set up the virtual environment and install dependencies
all: install

# Install development dependencies
install-dev:
	uv pip install -e ".[dev]"

# Remove virtual environment and cached Python files
clean:
	rm -rf $(VENV)
	rm -rf .uv
	rm -rf *.egg-info
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.ruff_cache' -delete
	find . -type d -name '.pytest_cache' -delete

# Format and lint all Python files using black and ruff
format:
	$(eval TARGET := $(if $(FILE),$(FILE),src/))
	black $(TARGET) --experimental-string-processing
	ruff check --fix $(TARGET)
	ruff format $(TARGET)

# Individual formatting commands
check:
	$(eval TARGET := $(if $(FILE),$(FILE),src/))
	ruff check $(TARGET)

# Run integration tests
integration: install-dev
	 && make -f src/tests/integration/Makefile $(TARGET)

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
	 $(PYTHON) src/votemarket_toolkit/commands/block_info.py \
		"$(BLOCK_NUMBER)"

get-active-campaigns: install
	 $(PYTHON) src/votemarket_toolkit/commands/active_campaigns.py \
		$(if $(CHAIN_ID),"--chain-id=$(CHAIN_ID)") \
		$(if $(PLATFORM),"--platform=$(PLATFORM)") \
		$(if $(PROTOCOL),"--protocol=$(PROTOCOL)")

get-epoch-blocks: install
	$(PYTHON) src/votemarket_toolkit/commands/get_epoch_blocks.py \
		"$(CHAIN_ID)" \
		"$(PLATFORM)" \
		"$(EPOCHS)"

# Display help information
help:
	@ $(PYTHON) src/votemarket_toolkit/commands/help.py
