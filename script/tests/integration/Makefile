MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
TEMP_DIR := $(MAKEFILE_DIR)temp
VENV_DIR := $(MAKEFILE_DIR)../../../venv
VENV_ACTIVATE := . $(VENV_DIR)/bin/activate

$(shell mkdir -p $(TEMP_DIR))

include .env
export

# Variables
ALCHEMY_KEY ?= $(ALCHEMY_KEY)
FORK_BLOCK_NUMBER ?= 259600302  # Deployment of VM on Arbitrum
ANVIL_PORT ?= 8545

# Targets
.PHONY: start-anvil stop-anvil run-scenario restore-snapshot clean

# Start Anvil
start-anvil:
	@echo "Starting Anvil..."
	@anvil --fork-url https://arb-mainnet.g.alchemy.com/v2/$(ALCHEMY_KEY) \
		--fork-block-number $(FORK_BLOCK_NUMBER) \
		--port $(ANVIL_PORT) > $(TEMP_DIR)/anvil.log 2>&1 & echo $$! > $(TEMP_DIR)/anvil.pid
	@echo "Anvil started with PID $$(cat $(TEMP_DIR)/anvil.pid). Logs are in $(TEMP_DIR)/anvil.log"

# Stop Anvil
stop-anvil:
	@echo "Stopping Anvil..."
	@lsof -t -i tcp:8545 | xargs kill
	@rm -f $(TEMP_DIR)/anvil.pid
	@rm -f $(TEMP_DIR)/anvil.log
	@rm -f $(TEMP_DIR)/snapshots.json

# Run Scenario
run-scenario: start-anvil
	@echo "Running Scenario $(SCENARIO)..."
	@$(VENV_ACTIVATE) && python script/tests/integration/scenario_$(SCENARIO).py
	@echo "Scenario $(SCENARIO) completed. Use 'make restore-snapshot SNAPSHOT=<snapshot_name>' to navigate to a specific point."

# Restore to a specific snapshot
restore-snapshot:
	@echo "Restoring to snapshot: $(SNAPSHOT)"
	@$(VENV_ACTIVATE) && python script/tests/integration/shared/snapshots.py $(SNAPSHOT)

# Clean up temporary files
clean:
	@echo "Cleaning up temporary files..."
	@rm -rf $(TEMP_DIR)

# Default target
all: run-scenario