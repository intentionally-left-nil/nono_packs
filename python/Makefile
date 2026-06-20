# Makefile — run JupyterLab under the nono python-sandbox pack.
#
# Usage:
#   make setup       — create the sandboxed conda prefix and sideload the pack
#   make jupyterlab  — launch JupyterLab inside the sandbox (opens in browser)
#   make clean       — remove the prefix and un-sideload the pack
#
# The PREFIX is a conda environment at /tmp/nono-jupyterlab-dev.
# It is intentionally separate from the test prefix (/tmp/nono-pypack-test)
# so that running tests and running JupyterLab interactively do not interfere.

CONDA        ?= conda
NONO         ?= nono-sideload
PACK_DIR     := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT    := $(abspath $(PACK_DIR)/..)

PREFIX       ?= /tmp/nono-jupyterlab-dev
PROFILE      := intentionally-left-nil/python
PORT         ?= 8888

.PHONY: help setup sideload jupyterlab clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  %-14s %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# setup: create the conda prefix + install JupyterLab + sideload the pack
# ---------------------------------------------------------------------------

setup: ## Create PREFIX, install JupyterLab, and sideload the pack
	@echo "==> Creating conda prefix at $(PREFIX)"
	@test -d "$(PREFIX)" \
		&& echo "    $(PREFIX) already exists, skipping conda create" \
		|| $(CONDA) create -p "$(PREFIX)" \
		       --override-channels -c defaults \
		       python=3.12 jupyterlab ipykernel \
		       --yes --quiet
	@echo "==> Sideloading the python pack"
	@$(MAKE) --no-print-directory sideload

sideload: ## (Re-)sideload the pack after editing policy.json or hooks
	@# Patch $PREFIX into policy.json, sideload, restore — same approach as conftest.py.
	@cp "$(PACK_DIR)/policy.json" "$(PACK_DIR)/policy.json.bak"
	@sed "s|\$$PREFIX|$(PREFIX)|g" "$(PACK_DIR)/policy.json.bak" \
		> "$(PACK_DIR)/policy.json"
	@$(NONO) sideload "$(PACK_DIR)" || (cp "$(PACK_DIR)/policy.json.bak" "$(PACK_DIR)/policy.json"; exit 1)
	@cp "$(PACK_DIR)/policy.json.bak" "$(PACK_DIR)/policy.json"
	@rm -f "$(PACK_DIR)/policy.json.bak"
	@echo "==> Pack sideloaded as $(PROFILE)"

# ---------------------------------------------------------------------------
# jupyterlab: launch JupyterLab inside the nono sandbox
# ---------------------------------------------------------------------------

jupyterlab: ## Launch JupyterLab inside the sandbox (Ctrl-C to stop)
	@test -d "$(PREFIX)" || (echo "ERROR: $(PREFIX) does not exist — run 'make setup' first" && exit 1)
	@echo "==> Starting JupyterLab at http://localhost:$(PORT)"
	@echo "    Sandboxed under profile: $(PROFILE)"
	@echo "    Prefix: $(PREFIX)"
	@echo ""
	CONDA_PREFIX="$(PREFIX)" \
	TMPDIR="$(PREFIX)/tmp" \
	$(NONO) run \
		--profile "$(PROFILE)" \
		--allow "$(PREFIX)" \
		--allow-cwd \
		-- \
		"$(PREFIX)/bin/python" -m jupyter lab \
			--no-browser \
			--port $(PORT) \
			--ip 127.0.0.1

# ---------------------------------------------------------------------------
# clean: remove the prefix and un-sideload the pack
# ---------------------------------------------------------------------------

clean: ## Remove PREFIX and un-sideload the pack
	@echo "==> Removing sideloaded pack"
	-$(NONO) remove "$(PROFILE)"
	@echo "==> Removing prefix $(PREFIX)"
	rm -rf "$(PREFIX)"
