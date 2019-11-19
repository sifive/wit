#!/bin/sh

. $(dirname $0)/test_util.sh

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

# Now set up repo bar to depend on foo, foo2, foo3
mkdir bar
git -C bar init

cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$PWD/foo" }
]
EOF

git -C bar add -A
git -C bar commit -m "commit1"
bar_commit=$(git -C bar rev-parse HEAD)

# Move foo and bar to another directory
mkdir newdir
mv foo bar newdir/

# Now create a workspace from bar
wit init myws -a bar

# Should fail because bar wasn't found
check "wit init with missing dependency fails" [ $? -ne 0 ]


wit --repo-path=$PWD/newdir init myws2 -a bar
check "wit with path set succeeds" [ $? -eq 0 ]

WIT_REPO_PATH=$PWD/newdir wit init myws3 -a bar
check "wit with \$WIT_REPO_PATH succeeds" [ $? -eq 0 ]

cd myws2

check "foo should be pulled in as a dependency of bar" [ -d foo ]
foo_ws_commit=$(git -C foo rev-parse HEAD)
check "foo commit should match the dependency in bar" [ "$foo_ws_commit" = "$foo_commit" ]

foo_lock_commit=$(jq -r '.foo.commit' wit-lock.json)
check "ws-lock.json should contain correct foo commit" [ "$foo_lock_commit" = "$foo_commit" ]

bar_lock_commit=$(jq -r '.bar.commit' wit-lock.json)
check "ws-lock.json should contain correct bar commit" [ "$bar_lock_commit" = "$bar_commit" ]

report
finish
