# storycraft-skills — developer tasks.
#
#   make check      CI gate: frontmatter/path/doc lint + inventory freshness
#   make lint       just the linter
#   make inventory  regenerate docs/SKILL-INVENTORY.md from frontmatter
#   make compile    syntax-check every script (no bytecode written)

PYTHON ?= python3

# Never leave __pycache__ behind: `make check` should not dirty the tree, and a
# stray bytecode dir under skills/ would show up in sync-check.sh's filesystem diff.
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help check lint inventory compile

help:
	@echo "make check      CI gate (lint + inventory freshness + syntax)"
	@echo "make lint       frontmatter / path / doc-drift lint"
	@echo "make inventory  regenerate docs/SKILL-INVENTORY.md"
	@echo "make compile    syntax-check all scripts (no bytecode written)"

check: lint
	$(PYTHON) tools/gen-inventory.py --check
	$(PYTHON) tools/compile-check.py

lint:
	$(PYTHON) tools/lint-skills.py

inventory:
	$(PYTHON) tools/gen-inventory.py

compile:
	$(PYTHON) tools/compile-check.py
