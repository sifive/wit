#!/bin/sh

. $(dirname $0)/test_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)

# foo ~= fizz
cp -r foo fizz
touch fizz/xyz
git -C fizz add -A
git -C fizz commit -m "fizz"
fizz_commit=$(git -C fizz rev-parse HEAD)
fizz_source="$PWD/fizz"

# bar depends on fizz
make_repo 'bar'
cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$fizz_commit", "name": "foo", "source": "$fizz_source" }
]
EOF
git -C bar add -A
git -C bar commit -m "add manifest"
bar_commit=$(git -C bar rev-parse HEAD)

# Now set up repo myws to depend on foo, bar
mkdir main_repo
git -C main_repo init

cat << EOF | jq . > main_repo/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$PWD/foo" },
    { "commit": "$bar_commit", "name": "bar", "source": "$PWD/bar" }
]
EOF

git -C main_repo add -A
git -C main_repo commit -m "commit1"
main_repo_commit=$(git -C main_repo rev-parse HEAD)

prereq "off"

# Now create a workspace from main_repo
wit init myws -a $PWD/main_repo

check "wit init with conflicting paths passes" [ $? -eq 0 ]

cd myws

foo_checked_out=$(git -C foo rev-parse HEAD)
check "foo should be checked out to the latest source version" [ "$foo_checked_out" = "$fizz_commit" ]


foo_origin=$(git -C foo remote get-url origin)
check "foo should be checked out to the latest source version" [ "$foo_origin" = "$fizz_source" ]

report
finish
