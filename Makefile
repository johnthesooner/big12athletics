PY ?= python3

.PHONY: install validate all check lint test clean

install:  ## install the package with dev tools
	$(PY) -m pip install -e ".[dev]"

validate:  ## check every input file
	ou-sec validate

all:  ## regenerate reports/ and docs/index.html
	ou-sec all

lint:
	ruff check src tests

test:
	$(PY) -m pytest

check: lint test  ## what CI runs

clean:
	find . -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache *.egg-info src/*.egg-info
