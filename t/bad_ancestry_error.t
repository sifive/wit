#!/usr/bin/env bash

# (the numbers are years)
#
# top:2019
# ├─ bar:2018
# │  └─ xyz:2010
# └─ foo:2017
#    └─ xyz:2011

. $(dirname $0)/regress_util.sh

prereq "on"

make_repo 'xyz'

cd xyz
touch one
git add -A
git commit -m "xyz:1"
xyz_commit_1=$(git rev-parse HEAD)

sleep 1

touch two
git add -A
git commit -m "xyz:2"
xyz_commit_2=$(git rev-parse HEAD)
cd ..

make_repo 'foo'
cat << EOF | jq . > foo/wit-manifest.json
[
    { "commit": "$xyz_commit_2", "name": "xyz", "source": "$PWD/xyz" }
]
EOF
git -C foo add -A
git -C foo commit -m "add xyz:2"
foo_commit=$(git -C foo rev-parse HEAD)

sleep 1

# Set up repo bar
make_repo 'bar'
cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$xyz_commit_1", "name": "xyz", "source": "$PWD/xyz" }
]
EOF
git -C bar add -A
git -C bar commit -m "add xyz:1"

prereq "off"

# Now create a workspace from main_repo
wit init myws -a $PWD/foo -a $PWD/bar
check "wit init should succeed" [ $? -eq 0 ]

cd myws

lock_xyz_commit=$(git -C xyz rev-parse HEAD)
check "wit should checkout the correct commit of xyz" [ "$lock_xyz_commit" = "$xyz_commit_2" ]

report
finish
