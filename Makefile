install_root := $(PREFIX)
version := $(shell cat lib/wit/version.py | grep -o '[.0-9]*')
install_dir := $(install_root)/$(version)

install:
	mkdir -p $(install_dir)
	cat .gitignore > .rsyncignore
	git ls-files -o >> .rsyncignore
	rsync -ar --include=wit --include='*.py' --exclude-from=.rsyncignore --exclude='actions/' --exclude='t/' --exclude='__pycache__/' --exclude='.*' --exclude='mypy.ini' --exclude='Makefile' . $(install_dir)


test-lint:
	flake8

test-typecheck:
	mypy lib/wit/*.py

test-regress:
	./t/test_all.sh

test-all: test-lint test-typecheck test-regress

.PHONY: install test-all test-lint test-typecheck test-regress
