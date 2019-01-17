#!/bin/sh

fail=0
pass=0

check() {
        check_name=$1
        shift;

        if $@
        then echo "${check_name} PASS"; ((pass++))
        else echo "${check_name} FAIL"; ((fail++))
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
