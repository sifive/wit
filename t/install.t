#!/usr/bin/env bash

. $(dirname $0)/test_util.sh

install_dir=$test_root/foo

make -C $wit_root install PREFIX=$install_dir
check "Installation should work" [ $? -eq 0 ]

wit_exe=$(find $install_dir -name 'wit' -type f)
echo $wit_exe
check "We should find the wit executable" [ ! -z "$wit_exe" ]

$wit_exe --version
check "Wit --version should execute" [ $? -eq 0 ]

report
finish
