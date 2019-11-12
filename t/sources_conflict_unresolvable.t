#!/bin/sh

. $(dirname $0)/test_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

sleep 1  # prevent duplicate commit hash on Travis (crazy)

mkdir newdir
cd newdir
# Set up repo foo
make_repo 'foo'
touch foo/xyz
git -C foo add -A
git -C foo commit -m "bump"
foo2_commit=$(git -C foo rev-parse HEAD)

cd ..


# Now set up repo main_repo to depend on both verrsions of foo
mkdir main_repo
git -C main_repo init

# two foo repos with different paths
cat << EOF | jq . > main_repo/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$PWD/foo" },
    { "commit": "$foo2_commit", "name": "foo", "source": "$PWD/newdir/foo" }
]
EOF
cat main_repo/wit-manifest.json

git -C main_repo add -A
git -C main_repo commit -m "commit1"
main_repo_commit=$(git -C main_repo rev-parse HEAD)

prereq "off"

# Now create a workspace from main_repo
output=$( wit init myws -a $PWD/main_repo 2>&1 )

# Should fail because of conflicting paths for foo
check "wit init with conflicting paths fails" [ $? -ne 0 ]

echo $output

echo $output | grep "Two dependencies have the same name"

check "error message is somewhat descriptive" [ $? -eq 0 ]

report
finish
