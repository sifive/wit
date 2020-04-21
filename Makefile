ifdef PREFIX
version := $(shell cat lib/wit/version.py | grep __version__ | cut -d= -f2 | tr -d ' "')
target_arg := --target=$(PREFIX)/$(version)
endif

install:
	python3 -m pip install $(target_arg) ./lib

test-lint:
	flake8

test-typecheck:
	mypy lib/wit/*.py

test-regress:
	./t/test_all.sh

test-all: test-lint test-typecheck test-regress

.PHONY: install test-all test-lint test-typecheck test-regress
