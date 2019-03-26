#!/bin/sh

. $(dirname $0)/regress_util.sh

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

# Set up repo foo2
make_repo 'foo2'
foo2_commit=$(git -C foo2 rev-parse HEAD)

# Set up repo foo3
make_repo 'foo3'
foo3_commit=$(git -C foo3 rev-parse HEAD)

# Now set up repo bar to depend on foo, foo2, foo3
mkdir bar
git -C bar init

cat << EOF | jq . > bar/wit-manifest.json
[
    {
        "commit": "$foo_commit",
        "name": "foo",
        "source": "$PWD/foo"
    },
    {
        "commit": "$foo2_commit",
        "name": "foo2",
        "source": "$PWD/foo2"
    },
    {
        "commit": "$foo3_commit",
        "name": "foo3",
        "source": "$PWD/foo3"
    }
]
EOF

git -C bar add -A
git -C bar commit -m "commit1"
bar_commit=$(git -C bar rev-parse HEAD)

# Move foo to another directory
mkdir newdir
mv foo newdir/

mkdir newdir2
mv foo2 newdir2/

# Now create a workspace from bar
wit init myws -a $PWD/bar

# Should fail because foo wasn't found
check "wit init with missing dependency fails" [ "$?" != 0 ]


wit --repo-path=$PWD:$PWD/newdir:$PWD/newdir2 init myws2 -a $PWD/bar
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
