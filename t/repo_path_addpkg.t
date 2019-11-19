#!/bin/sh

. $(dirname $0)/test_util.sh

prereq on

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
    { "commit": "$foo_commit", "name": "foo", "source": "$PWD/foo" },
    { "commit": "$foo2_commit", "name": "foo2", "source": "$PWD/foo2" },
    { "commit": "$foo3_commit", "name": "foo3", "source": "$PWD/foo3" }
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

original_dir=$PWD

prereq off


# Now create a workspace from bar
wit init myws
cd myws
wit --repo-path="$original_dir $original_dir/newdir $original_dir/newdir2" add-pkg bar
check "wit add-pkg with repo-path works" [ $? -eq 0 ]



report
finish
