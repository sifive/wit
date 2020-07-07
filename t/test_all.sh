#!/usr/bin/env bash

# To be fixed -- -j specifies number of parallel tests
OPT_J=1
#while getopts "j:" opt; do
#    case $opt in
#        j) OPT_J=$OPTARG ;;
#    esac
#done

echo "Running [$OPT_J] tests in parallel."

. $(dirname $0)/test_util.sh

## List of tests to ignore
test_ignore_list=( test_fail )
ignore_test () {
    local test_name=$1

    if [[ "${test_ignore_list[@]}" =~ "${test_name}" ]]
    then return 0
    else return 1
    fi
}

timestamp=`date +'%Y-%m-%dT%H-%M-%S'`
test_dir=${wit_root}/test.${timestamp}
echo "Running tests in ${test_dir}"
mkdir $test_dir

declare -A test_results
pass=0
fail=0
for test_path in $test_root/*.t; do
    cd $test_dir
    test_file=$(basename $test_path)
    test_name="${test_file%%.*}"

    if ignore_test $test_name
    then continue
    fi

    printf "Running test [$test_name]: "
    output=$({
        mkdir $test_name
        cd $test_name
        $test_path
    } 2>&1 )

    if [ $? -eq 0 ]; then
        test_results["$test_name"]="PASS"
        touch "PASS"
        ((pass++))
        echo "${test_results[$test_name]}";
    else
        test_results["$test_name"]="FAIL"
        touch "FAIL"
        ((fail++))
        test_result=1
        echo "${test_results[$test_name]}";
        echo "$output"
    fi
done

echo
echo
echo "Results:"
echo "Passing: $pass"
echo "Failing: $fail"

if ! [ -x "$(command -v jq)" ]; then
    echo "Some tests may have failed due to jq not being found"
fi

if ! [ -x "$(command -v java)" ]; then
    echo "Some tests may have failed due to java not being found"
fi

if [ $fail -ne 0 ]
then exit 1
else exit 0
fi
