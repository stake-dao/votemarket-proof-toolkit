# Makefile for VoteMarket Toolkit

# Configuration
PYTHON := uv run
VENV := .venv

# Phony targets declaration
.PHONY: all install install-dev clean format lint
.PHONY: build deploy clean-build test-build release
.PHONY: user-proof gauge-proof block-info
.PHONY: user-campaign-status check-user-eligibility get-active-campaigns get-epoch-blocks index-votes
.PHONY: vm
.PHONY: install-ts simulate simulate-ts

# Positional arguments support for user-campaign-status target
ifneq ($(filter user-campaign-status,$(MAKECMDGOALS)),)
USER_CAMPAIGN_STATUS_ARGS := $(filter-out user-campaign-status,$(MAKECMDGOALS))
ifneq ($(strip $(USER_CAMPAIGN_STATUS_ARGS)),)
USER_ADDRESS ?= $(firstword $(USER_CAMPAIGN_STATUS_ARGS))
$(foreach arg,$(USER_CAMPAIGN_STATUS_ARGS),$(eval $(arg):;@:))
endif
endif

# Default target
all: install

# Installation
install:
	@echo "Installing votemarket-toolkit..."
	uv sync

install-dev:
	uv pip install -e ".[dev]"

# Development
format:
	$(eval TARGET := $(if $(FILE),$(FILE),votemarket_toolkit/))
	uv run black $(TARGET)
	uv run ruff check --fix $(TARGET)
	uv run ruff format $(TARGET)

lint:
	uv run ruff check votemarket_toolkit/

clean:
	rm -rf $(VENV) .uv *.egg-info
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.ruff_cache' -delete
	find . -type d -name '.pytest_cache' -delete

# Building and Publishing
build:
	@echo "Building package..."
	rm -rf dist/ build/ *.egg-info
	uv build
	@echo "Build complete. Files in dist/"
	@ls -la dist/

deploy:
	@echo "Deploying to PyPI..."
	@if [ -z "$$UV_PUBLISH_TOKEN" ]; then \
		echo "Error: UV_PUBLISH_TOKEN not set. Get token from https://pypi.org/manage/account/token/"; \
		echo "Then run: export UV_PUBLISH_TOKEN=pypi-your-token"; \
		exit 1; \
	fi
	uv publish --token $$UV_PUBLISH_TOKEN
	@echo "Deploy complete!"

clean-build:
	rm -rf dist/ build/ *.egg-info src/*.egg-info

test-build:
	@echo "Testing build locally..."
	uv venv test-env
	. test-env/bin/activate && uv pip install dist/*.whl
	. test-env/bin/activate && python -c "from votemarket_toolkit.shared import registry; print('✅ Import successful')"
	rm -rf test-env
	@echo "Test successful!"

release: clean-build build
	@echo "Ready to release. Run 'make deploy' to upload to PyPI"

# Proof Generation Commands
user-proof:
	$(PYTHON) votemarket_toolkit/commands/user_proof.py \
		--protocol=$(PROTOCOL) \
		--gauge-address=$(GAUGE_ADDRESS) \
		--user-address=$(USER_ADDRESS) \
		--block-number=$(BLOCK_NUMBER)

gauge-proof:
	$(PYTHON) votemarket_toolkit/commands/gauge_proof.py \
		--protocol=$(PROTOCOL) \
		--gauge-address=$(GAUGE_ADDRESS) \
		--current-epoch=$(CURRENT_EPOCH) \
		--block-number=$(BLOCK_NUMBER)

# Information Retrieval Commands
block-info:
	$(PYTHON) votemarket_toolkit/commands/block_info.py \
		--block-number=$(BLOCK_NUMBER)

user-campaign-status:
	$(PYTHON) votemarket_toolkit/commands/user_campaign_status.py \
		$(if $(CHAIN_ID),--chain-id=$(CHAIN_ID)) \
		$(if $(PLATFORM),--platform=$(PLATFORM)) \
		$(if $(CAMPAIGN_ID),--campaign-id=$(CAMPAIGN_ID)) \
		$(if $(USER_ADDRESS),--user=$(USER_ADDRESS)) \
		$(if $(BRIEF),--brief) \
		$(if $(FORMAT),--format=$(FORMAT)) \
		$(if $(LIST_AVAILABLE),--list-available) \
		$(if $(INTERACTIVE),--interactive)

check-user-eligibility:
	$(PYTHON) votemarket_toolkit/commands/check_user_eligibility.py \
		--user=$(USER) \
		--protocol=$(PROTOCOL) \
		$(if $(GAUGE),--gauge=$(GAUGE)) \
		$(if $(CHAIN_ID),--chain-id=$(CHAIN_ID))

get-active-campaigns:
	$(PYTHON) votemarket_toolkit/commands/active_campaigns.py \
		$(if $(CHAIN_ID),--chain-id=$(CHAIN_ID)) \
		$(if $(PLATFORM),--platform=$(PLATFORM)) \
		$(if $(PROTOCOL),--protocol=$(PROTOCOL)) \
		$(if $(CAMPAIGN_ID),--campaign-id=$(CAMPAIGN_ID))

get-epoch-blocks:
	$(PYTHON) votemarket_toolkit/commands/get_epoch_blocks.py \
		$(if $(CHAIN_ID),--chain-id=$(CHAIN_ID)) \
		$(if $(PLATFORM),--platform=$(PLATFORM)) \
		$(if $(EPOCHS),--epochs=$(EPOCHS))

index-votes:
	$(PYTHON) votemarket_toolkit/commands/index_votes.py \
		$(if $(PROTOCOL),--protocol=$(PROTOCOL)) \
		$(if $(GAUGE_ADDRESS),--gauge-address=$(GAUGE_ADDRESS))

# CCIP Simulation
simulate:
	$(PYTHON) votemarket_toolkit/utils/ccip/gas_estimator.py \
		--adapter=0xbF0000F5C600B1a84FE08F8d0013002ebC0064fe \
		--laposte=0xF0000058000021003E4754dCA700C766DE7601C2 \
		--to-address=0xADfBFd06633eB92fc9b58b3152Fe92B0A24eB1FF \
		--tokens 0x41D5D79431A913C4aE7d69a668ecdfE5fF9DFB68 0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F 0x090185f2135308BaD17527004364eBcC2D37e5F6 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 0x30D20208d987713f46DFD34EF128Bb16C404D10f

# TypeScript/Node Commands
install-ts:
	npm install

simulate-ts:
	cd examples/typescript && npm run simulate -- \
		--adapter="0xbF0000F5C600B1a84FE08F8d0013002ebC0064fe" \
		--laposte="0xF0000058000021003E4754dCA700C766DE7601C2" \
		--to-address="0x5e5C922a5Eeab508486eB906ebE7bDFFB05D81e5" \
		--tokens 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 0x090185f2135308BaD17527004364eBcC2D37e5F6 0x41d5d79431a913c4ae7d69a668ecdfe5ff9dfb68 0x30d20208d987713f46dfd34ef128bb16c404d10f

# Unified CLI wrapper
vm:
	$(PYTHON) -m votemarket_toolkit.cli $(ARGS)
