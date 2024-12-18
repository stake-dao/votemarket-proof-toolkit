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
