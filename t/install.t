#!/usr/bin/env bash

. $(dirname $0)/regress_util.sh

install_dir=$test_root/foo

make -C $wit_root install PREFIX=$install_dir
check "Installation should work" [ $? -eq 0 ]

wit_exe=$(find $install_dir -name 'wit' -type f)
echo $wit_exe
check "We should find the wit executable" [ ! -z "$wit_exe" ]

$wit_exe -vvvv --version | grep -q 'Version as read from'
check "Wit logging should tell us it read from __version__" [ $? -eq 0 ]

report
finish
