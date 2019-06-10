#!/usr/bin/env bash

# To be fixed -- -j specifies number of parallel tests
OPT_J=1
#while getopts "j:" opt; do
#    case $opt in
#        j) OPT_J=$OPTARG ;;
#    esac
#done

echo "Running [$OPT_J] tests in parallel."

. $(dirname $0)/regress_util.sh

## List of tests to ignore
test_ignore_list=( test_fail )
ignore_test () {
    local test_name=$1

    if [[ "${test_ignore_list[@]}" =~ "${test_name}" ]]
    then return 0
    else return 1
    fi
}

export PATH=$wit_root:${PATH}

timestamp=`date +'%Y-%m-%dT%H-%M-%S'`
regression_dir=${wit_root}/regression.${timestamp}
echo "Running tests in ${regression_dir}"
mkdir $regression_dir

declare -A test_results
pass=0
fail=0
for test_path in $test_root/*.t; do
    cd $regression_dir
    test_file=$(basename $test_path)
    test_name="${test_file%%.*}"

    if ignore_test $test_name
    then continue
    fi

    echo "Running test [$test_name]"
    mkdir $test_name
    cd $test_name

    $test_path >& output
    if [ $? -eq 0 ]; then
        test_results["$test_name"]="PASS"
        touch "PASS"
        ((pass++))
    else
        test_results["$test_name"]="FAIL"
        touch "FAIL"
        ((fail++))
        regression_result=1
    fi
done

for test_name in ${!test_results[@]}; do echo "${test_results[$test_name]} - ${test_name}"; done

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
