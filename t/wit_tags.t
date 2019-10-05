#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq on

into_test_dir

# Set up repo foo
make_repo 'foo'
foo_commit=$(git -C foo rev-parse HEAD)
foo_dir=$PWD/foo
# Add a second commit
echo "halp" > foo/file2
git -C foo add -A
git -C foo commit -m "commit2"
git -C foo tag "v1.0.0"
foo_commit2=$(git -C foo rev-parse HEAD)
echo "yo" > foo/file3
git -C foo add -A
git -C foo commit -m "commit3"
git -C foo tag "some-tag"
git -C foo tag "v2.0.0"
foo_commit3=$(git -C foo rev-parse HEAD)

make_repo 'bar'
# Make bar depend on foo
cat << EOF | jq . > bar/wit-manifest.json
[
    { "commit": "$foo_commit", "name": "foo", "source": "$foo_dir" }
]
EOF
git -C bar add -A
git -C bar commit -m "commit2"
bar_dir=$PWD/bar

prereq off

# ********** Tests of a package in the workspace **********
wit init ws1
cd ws1
wit add-pkg $foo_dir
jq -re '.[] | select(.name=="foo") | .tag' wit-workspace.json
check "Cloning from remote with no specified tag should NOT have a tag" [ $? -eq 1 ]

wit update-pkg foo::v1.0.0
foo_ws_tag=$(jq -r '.[] | select(.name=="foo") | .tag' wit-workspace.json)
check "Updating a package with a specified tag should have a tag" [ "$foo_ws_tag" = "v1.0.0" ]

## TODO Unfortunately this may not be possible
#git -C foo checkout v2.0.0
#wit update-pkg foo
#foo_ws_tag=$(jq -r '.[] | select(.name=="foo") | .tag' wit-workspace.json)
#msg="Updating a package with no specified revision but checked out tag should have a tag"
#check "$msg" [ "$foo_ws_tag" = "v2.0.0" ]

cd ..
wit init ws2
cd ws2
wit add-pkg $foo_dir::v1.0.0
foo_ws_tag=$(jq -r '.[] | select(.name=="foo") | .tag' wit-workspace.json)
check "Cloning from remote with specified tag should have a tag" [ "$foo_ws_tag" = "v1.0.0" ]

cd ..
wit init ws3
cd ws3
git clone $foo_dir
wit add-pkg foo
jq -re '.[] | select(.name=="foo") | .tag' wit-workspace.json
check "Adding a cloned repo with no specified tag and no tag checked out should NOT have a tag" [ $? -eq 1 ]

## TODO Unfortunately this may not be possible
#cd ..
#wit init ws4
#cd ws4
#git clone $foo_dir
#git -C foo checkout v1.0.0
#wit add-pkg foo
#foo_ws_tag=$(jq -r '.[] | select(.name=="foo") | .tag' wit-workspace.json)
#check "Adding a cloned repo with a tag checked out *should* have a tag" [ "$foo_ws_tag" = "v1.0.0" ]

# ********** Tests of a dependency of another package **********
cd ..
wit init ws5 -a $bar_dir
cd ws5

wit -C bar update-dep foo::v1.0.0
check "Updating foo to a tag should work" [ $? -eq 0 ]

foo_dep_commit=$(jq -r '.[] | select(.name=="foo") | .commit' bar/wit-manifest.json)
check "Foos commit in bar's manifest should have bumped" [ "$foo_dep_commit" = "$foo_commit2" ]

foo_dep_tag=$(jq -r '.[] | select(.name=="foo") | .tag' bar/wit-manifest.json)
check "Foo in bar's manifest should have have a tag" [ "$foo_dep_tag" = "v1.0.0" ]

check "Checked out foo commit should be unchanged" [ "$(git -C foo rev-parse HEAD)" = "$foo_commit" ]

# Bump foo in bar
git -C bar add -A
git -C bar commit -m "bump foo to v1.0.0"
# Now update the workspace with the bump
wit update-pkg bar
wit update

check "Checked out foo commit should have bumped" [ "$(git -C foo rev-parse HEAD)" = "$foo_commit2" ]

foo_lock_commit=$(jq -r '.foo.commit' wit-lock.json)
check "Lock file should contain foo commit" [ "$foo_lock_commit" = "$foo_commit2" ]

foo_lock_tag=$(jq -r '.foo.tag' wit-lock.json)
check "Lock file should contain foo tag" [ "$foo_lock_tag" = "v1.0.0" ]

#wit -C bar update-dep foo::origin/master
#jq -re '.[] | select(.name=="foo") | .tag' bar/wit-manifest.json
#check "When no tag is specified, don't have one" [ $? -eq 1 ]
#
### TODO Unfortunately this may not be possible
##git -C foo checkout v2.0.0
##wit -C bar update-dep foo
##foo_dep_tag=$(jq -r '.[] | select(.name=="foo") | .tag' bar/wit-manifest.json)
##check "When no revision is specified but a tag is checked out, have the tag" [ "$foo_dep_tag" = "v2.0.0" ]
#
#wit -C bar update-dep foo::some-tag
#foo_dep_tag=$(jq -r '.[] | select(.name=="foo") | .tag' bar/wit-manifest.json)
#check "Support specifying the tag" [ "$foo_dep_tag" = "some-tag" ]

report
finish
