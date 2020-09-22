#!/bin/sh
. $(dirname $0)/test_util.sh
prereq on


# Set up repo foo to use as a package
make_repo 'foo'
foo_dir=$PWD/foo

# 'baa' to use as wit-manifest-dependency of 'foo'
make_repo 'baa'
baa_dir=$PWD/baa

# 'xyz' to use as submodule dependency of 'baa'
make_repo 'xyz'
xyz_dir=$PWD/xyz

# add xyz as submodule dependency of baa, but ignored
(
  cd $baa_dir
  git submodule add $xyz_dir
  printf "\twit = ignore\n" >> .gitmodules
  git commit -am "add submodule dep"
)
baa_commit=$(git -C baa rev-parse HEAD)

# add baa as wit-dependency of foo
(
  cd $foo_dir
  echo "[{\"name\":\"baa\", \"commit\":\"$baa_commit\", \"source\":\"$baa_dir\"}]" > wit-manifest.json
  git add wit-manifest.json
  git commit -m "add wit dep"
)


prereq off

wit init ws -a $foo_dir
RES=$?
check "wit init should work" [ $RES -eq 0 ]

cd ws

ls | grep xyz
RES=$?
check "ignored repo should not be found in workspace" [ $RES -eq 1 ]

report
finish
