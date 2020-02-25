#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

BASE_DIR=$PWD

wit init myws

for NUM in 1 2 3; do
    cd $BASE_DIR
    make_bare_repo foo${NUM}
    make_bare_repo baa${NUM}

    # Add the foo repos as packages in the workspace
    cd myws
    wit add-pkg $BASE_DIR/foo${NUM}
    wit update

    # Add the baa repos as dependencies on foo repos
    cd foo${NUM}
    wit add-dep $BASE_DIR/baa${NUM}
    git add wit-manifest.json
    git commit -m "added dep baa${NUM}"
    git push
    wit update-pkg foo${NUM}
    wit update
done

prereq off

cd $BASE_DIR

mkdir second-ws
cp  myws/wit-lock.json myws/wit-workspace.json second-ws/
cd second-ws

wit restore

cd $BASE_DIR

diff myws/wit-workspace.json second-ws/wit-workspace.json
check "wit-workspace.json files should be the same" [ $? -eq 0 ]

diff myws/wit-lock.json second-ws/wit-lock.json
check "wit-lock.json files should be the same" [ $? -eq 0 ]

# Ensure that the two workspaces have the same git checkouts
for NUM in 1 2 3; do
    for PREFIX in foo baa; do
      first=$(git -C myws/${PREFIX}${NUM} rev-parse HEAD)
      second=$(git -C second-ws/${PREFIX}${NUM} rev-parse HEAD)
      check "commit SHA-1s should be the same" [ $first = $second ]
    done
done

report
finish
