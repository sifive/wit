#!/bin/sh

fail=0
pass=0

check() {
        check_name=$1
        shift;

        if $@
        then echo "PASS - ${check_name}"; ((pass++))
        else echo "FAIL - ${check_name}"; ((fail++))
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
