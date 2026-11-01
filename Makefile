# storycraft-skills — developer tasks.
#
#   make check      CI gate: lint + inventory + syntax + eval + smoke
#   make lint       just the linter
#   make inventory  regenerate docs/SKILL-INVENTORY.md from frontmatter
#   make compile    syntax-check every script (Python + shell; no bytecode written)
#   make eval       run the scripts against fixtures with known defects
#   make smoke      scaffold a throwaway project end-to-end and assert its tree

PYTHON ?= python3

# Never leave __pycache__ behind: `make check` should not dirty the tree, and a
# stray bytecode dir under skills/ would show up in sync-check.sh's filesystem diff.
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help check lint inventory compile eval smoke eval-editorial export-eval

help:
	@echo "make check      CI gate (lint + inventory freshness + syntax + eval + smoke)"
	@echo "make lint       frontmatter / path / doc-drift lint"
	@echo "make inventory  regenerate docs/SKILL-INVENTORY.md"
	@echo "make compile    syntax-check all scripts (Python + shell, no bytecode)"
	@echo "make eval       run the scripts against fixtures with known defects"
	@echo "make smoke      scaffold a project end-to-end and assert the tree"

# CI runs this target — keep the recipe here the single source of the gate, so
# the Makefile can never drift out of sync with what CI actually enforces.
check: lint inventory-check compile eval smoke

lint:
	$(PYTHON) tools/lint-skills.py

inventory:
	$(PYTHON) tools/gen-inventory.py

inventory-check:
	$(PYTHON) tools/gen-inventory.py --check

compile:
	$(PYTHON) tools/compile-check.py

eval:
	bash tools/eval-skills.sh
	$(PYTHON) tools/test-storycraft-state.py

smoke:
	bash tools/smoke-new-book.sh

# Emits neutral packets; literary author scoring stays explicit.
eval-editorial:
	$(PYTHON) tools/eval-editorial.py --packets /tmp/storycraft-editorial-packets

export-eval:
	$(PYTHON) tools/eval-exports.py
