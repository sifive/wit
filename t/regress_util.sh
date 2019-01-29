#!/bin/sh

wit_repo='git@github.com:sifive/wit'
test_root=$(dirname $(perl -MCwd -e "print Cwd::realpath('$0')"))
wit_root=$(perl -MCwd -e "print Cwd::realpath('$test_root/..')")

export PATH=$wit_root:${PATH}

fail=0
pass=0

check() {
        check_name=$1
        shift;

        if $@
        then echo "PASS - ${check_name}"; pass=$((pass+1))
        else echo "FAIL - ${check_name}"; fail=$((fail+1))
        fi
}

report() {
        echo "PASS: $pass"
        echo "FAIL: $fail"
}

finish() {
        if [ $fail -eq 0 ]
        then echo "Test passed"; exit 0
        else echo "Test failed"; exit 1
        fi
}
