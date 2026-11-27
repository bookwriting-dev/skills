# storycraft-skills — developer tasks.
#
#   make check      CI gate: lint + inventory + syntax + eval + smoke
#   make lint       just the linter
#   make inventory  regenerate docs/SKILL-INVENTORY.md from frontmatter
#   make compile    syntax-check every script (Python + shell; no bytecode written)
#   make eval       run the scripts against fixtures with known defects
#   make smoke      scaffold a throwaway project end-to-end and assert its tree

PYTHON ?= python3
UV ?= uv
BOOKS_DIR ?= $(HOME)/Projects/Books
DESKTOP_PLUGIN_DIR ?= $(HOME)/Plugins
CLAUDE_MARKETPLACE_DIR ?= $(CURDIR)/dist/claude-marketplace

# Never leave __pycache__ behind: `make check` should not dirty the tree, and a
# stray bytecode dir under skills/ would show up in sync-check.sh's filesystem diff.
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help check lint inventory inventory-check compile eval smoke eval-editorial eval-routing export-eval status-projects plugin-dist desktop-plugin check-plugin install-plugin
.PHONY: claude-plugin check-claude-plugin

help:
	@echo "make check      CI gate (lint + inventory freshness + syntax + eval + smoke)"
	@echo "make lint       frontmatter / path / doc-drift lint"
	@echo "make inventory  regenerate docs/SKILL-INVENTORY.md"
	@echo "make compile    syntax-check all scripts (Python + shell, no bytecode)"
	@echo "make eval       run the scripts against fixtures with known defects"
	@echo "make smoke      scaffold a project end-to-end and assert the tree"
	@echo "make eval-routing  run the live Codex routing evaluation"
	@echo "make status-projects  scan BOOKS_DIR for pinned library version drift"
	@echo "make install-plugin   build and refresh the personal ChatGPT Desktop plugin"
	@echo "make check-plugin     test one desktop package against two manuscript repos"
	@echo "make claude-plugin    build the local Claude Code marketplace"
	@echo "make check-claude-plugin  test a Claude installation and cross-host review freshness"

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
	$(PYTHON) tools/test-state-regressions.py
	$(PYTHON) tools/test-novel-draft-packet.py
	$(PYTHON) tools/test-draft-promises.py
	$(PYTHON) tools/test-novel-beta.py
	$(PYTHON) tools/test-drafting-study.py
	$(PYTHON) tools/test-storycraft-improvements.py
	$(PYTHON) tools/test-edition-exchange.py
	$(PYTHON) tools/test-editorial-milestones.py
	$(PYTHON) tools/test-author-read.py
	$(PYTHON) tools/test-storycraft-mcp.py
	$(PYTHON) tools/eval-routing.py --check-fixtures

smoke:
	bash tools/smoke-new-book.sh

# Emits neutral packets; literary author scoring stays explicit.
eval-editorial:
	$(PYTHON) tools/eval-editorial.py --packets /tmp/storycraft-editorial-packets

eval-routing:
	$(PYTHON) tools/eval-routing.py --live $(ROUTING_ARGS)

export-eval:
	$(PYTHON) tools/test-edition-exchange.py
	$(PYTHON) tools/eval-exports.py
	$(PYTHON) tools/test-storycraft-improvements.py StorycraftImprovements.test_returned_word_comments_match_anchored_edition

status-projects:
	$(PYTHON) tools/update-project.py --scan-dir "$(BOOKS_DIR)"

plugin-dist:
	@rm -rf dist/storycraft-skills
	@mkdir -p dist/storycraft-skills/rules dist/storycraft-skills/mcp
	@cp plugin/plugin.json plugin/mcp_config.json dist/storycraft-skills/
	@cp mcp/storycraft_mcp.py dist/storycraft-skills/mcp/
	@sed -e 's|__SERIES_TITLE__|Storycraft Suite|g' -e 's|__PROJECT_TYPE__|FICTION, NONFICTION, or HYBRID|g' templates/AGENTS.md > dist/storycraft-skills/rules/AGENTS.md
	@$(PYTHON) -c "import shutil; shutil.copytree('skills', 'dist/storycraft-skills/skills', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))"
	@echo "Built plugin bundle at dist/storycraft-skills"

desktop-plugin:
	$(UV) run --no-project --with 'PyYAML==6.0.3' python tools/build-desktop-plugin.py "$(DESKTOP_PLUGIN_DIR)/storycraft"

check-plugin:
	$(UV) run --no-project --with 'PyYAML==6.0.3' python tools/test-desktop-plugin.py

install-plugin:
	$(UV) run --no-project --with 'PyYAML==6.0.3' python tools/build-desktop-plugin.py "$(DESKTOP_PLUGIN_DIR)/storycraft" --install

claude-plugin:
	$(UV) run --no-project --with 'PyYAML==6.0.3' python tools/build-claude-plugin.py "$(CLAUDE_MARKETPLACE_DIR)"

check-claude-plugin:
	$(UV) run --no-project --with 'PyYAML==6.0.3' python tools/test-claude-plugin.py
