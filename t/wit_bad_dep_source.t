#!/bin/bash

. $(dirname $0)/test_util.sh

prereq "on"

START_DIR=$PWD

make_repo 'parent'
make_repo 'depend'
depend_dir="$PWD/depend"

prereq "off"


##############
# Adding a dependency

wit init ws -a ./parent
cd ws

cd parent
wit add-dep ${depend_dir}
git commit -am "add dep"
git push origin HEAD:main
cd ..

##############
# Trying to clone the dependency, but its missing now

cd $START_DIR
rm -rf depend
wit init ws2 -a ./parent &> out
RES=$?
check "fail to clone with the missing dependency" [ $RES -ne 0 ]

grep -q "Bad remote" out
RES=$?
check "error message should highlight issue" [ $RES -eq 0 ]


