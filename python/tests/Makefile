# Makefile for the nono python pack test suite.
#
# The *sandboxed* prefix (/tmp/nono-pypack-test) is managed by the pytest
# fixtures in conftest.py, not here.

CONDA    ?= conda
ENV_DIR  := .env

.PHONY: setup test clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  %-10s %s\n", $$1, $$2}'

setup: ## Create the conda environment that pytest runs in (once)
	@test -d $(ENV_DIR) \
		&& echo "$(ENV_DIR) already exists, skipping" \
		|| $(CONDA) create -p $(ENV_DIR) --override-channels -c defaults python=3.12 pytest --yes

test: ## Run the full test suite
	$(CONDA) run --no-capture-output -p $(ENV_DIR) python -m pytest .. -v $(PYTEST_ARGS)

clean: ## Remove the test runner environment
	rm -rf $(ENV_DIR)
