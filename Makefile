# Makefile for VoteMarket Proofs Generation

# Configuration
PYTHON := python3
VENV := venv
VENV_ACTIVATE := . $(VENV)/bin/activate
SRC_DIR := script

# Phony targets declaration
.PHONY: all install clean test help integration
.PHONY: user-proof gauge-proof block-info get-active-campaigns get-epoch-blocks
.PHONY: format lint

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

# Format all Python files
format:
	black --line-length 79 .
	isort -rc .
	autoflake -r --in-place --remove-all-unused-imports --remove-unused-variables .

# Format Python files. Usage: make format [FILE=path/to/file]
format:
	$(eval TARGET := $(if $(FILE),$(FILE),script/))
	black --line-length 79 $(TARGET)
	isort $(TARGET)
	autoflake -r --in-place --remove-all-unused-imports --remove-unused-variables $(TARGET)

black:
	$(eval TARGET := $(if $(FILE),$(FILE),script/))
	black --line-length 79 $(TARGET)

isort:
	$(eval TARGET := $(if $(FILE),$(FILE),script/))
	isort $(TARGET)

autoflake:
	$(eval TARGET := $(if $(FILE),$(FILE),script/))
	autoflake -r --in-place --remove-all-unused-imports --remove-unused-variables $(TARGET)

# Run integration tests
integration:
	$(VENV_ACTIVATE) && make -f script/tests/integration/Makefile $(TARGET)

# Proof generation commands
user-proof: install
	$(VENV_ACTIVATE) && PYTHONPATH=script $(PYTHON) script/commands/user_proof.py \
		"$(PROTOCOL)" \
		"$(GAUGE_ADDRESS)" \
		"$(USER_ADDRESS)" \
		"$(BLOCK_NUMBER)"

gauge-proof: install
	$(VENV_ACTIVATE) && PYTHONPATH=script $(PYTHON) script/commands/gauge_proof.py \
		"$(PROTOCOL)" \
		"$(GAUGE_ADDRESS)" \
		"$(CURRENT_EPOCH)" \
		"$(BLOCK_NUMBER)"

# Information retrieval commands
block-info: install
	$(VENV_ACTIVATE) && PYTHONPATH=script $(PYTHON) script/commands/block_info.py \
		"$(BLOCK_NUMBER)"

get-active-campaigns: install
	$(VENV_ACTIVATE) && PYTHONPATH=script $(PYTHON) script/commands/active_campaigns.py \
		"$(CHAIN_ID)" \
		"$(PLATFORM)"

get-epoch-blocks: install
	$(VENV_ACTIVATE) && PYTHONPATH=script $(PYTHON) script/commands/get_epoch_blocks.py \
		"$(CHAIN_ID)" \
		"$(PLATFORM)" \
		"$(EPOCHS)"

# Display help information
help:
	@$(VENV_ACTIVATE) && PYTHONPATH=script $(PYTHON) script/commands/help.py
