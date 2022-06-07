# NOTE: Used on linux, limited support outside of Linux
#
# A simple makefile to help with small tasks related to development of pynisher
# These have been configured to only really run short tasks. Longer form tasks
# are usually completed in github actions.

.PHONY: help install-dev check format pre-commit clean clean-build build links publish test

help:
	@echo "Makefile pynisher"
	@echo "* install-dev      to install all dev requirements and install pre-commit"
	@echo "* check            to check the source code for issues"
	@echo "* format           to format the code with black and isort"
	@echo "* pre-commit       to run the pre-commit check"
	@echo "* clean            to clean the dist
	@echo "* build            to build a dist"
	@echo "* publish          to help publish the current branch to pypi"
	@echo "* test             to run the tests"

PYTHON ?= python
CYTHON ?= cython
PYTEST ?= python -m pytest
CTAGS ?= ctags
PIP ?= python -m pip
MAKE ?= make
BLACK ?= black
ISORT ?= isort
PYDOCSTYLE ?= pydocstyle
MYPY ?= mypy
PRECOMMIT ?= pre-commit
FLAKE8 ?= flake8

DIR := "${CURDIR}"
DIST := "${CURDIR}/dist""
INDEX_HTML := "file://${DOCDIR}/build/html/index.html"

install-dev:
	$(PIP) install -e ".[test]"
	pre-commit install

check-black:
	$(BLACK) pynisher test --check || :

check-isort:
	$(ISORT) pynisher test --check || :

check-pydocstyle:
	$(PYDOCSTYLE) pynisher || :

check-mypy:
	$(MYPY) pynisher || :

check-flake8:
	$(FLAKE8) pynisher || :
	$(FLAKE8) test || :

# pydocstyle does not have easy ignore rules, instead, we include as they are covered
check: check-black check-isort check-mypy check-flake8 check-pydocstyle

pre-commit:
	$(PRECOMMIT) run --all-files

format-black:
	$(BLACK) pynisher/.*
	$(BLACK) test/.*

format-isort:
	$(ISORT) pynisher
	$(ISORT) test


format: format-black format-isort

clean-build:
	$(PYTHON) setup.py clean
	rm -rf ${DIST}

# Clean up any builds in ./dist
clean: clean-build

# Build a distribution in ./dist
build:
	$(PYTHON) setup.py sdist

examples:
	@echo "TODO"

# Publish to testpypi
# Will echo the commands to actually publish to be run to publish to actual PyPi
# This is done to prevent accidental publishing but provide the same conveniences
publish: clean build
	$(PIP) install twine
	$(PYTHON) -m twine upload --repository testpypi ${DIST}/*
	@echo
	@echo "Test with the following:"
	@echo "* Create a new virtual environment to install the uplaoded distribution into"
	@echo "* Run the following:"
	@echo
	@echo "        pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/pynisher"
	@echo
	@echo "* Run this to make sure it can import correctly, plus whatever else you'd like to test:"
	@echo
	@echo "        python -c 'import pynisher'"
	@echo
	@echo "Once you have decided it works, publish to actual pypi with"
	@echo
	@echo "    python -m twine upload dist/*"

test:
	$(PYTEST) test
