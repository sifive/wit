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

make_repo 'abc'
abc_dir=$PWD/abc

# add xyz as submodule dependency of baa
(
  cd $baa_dir
  git submodule add $xyz_dir
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

wit inspect --tree | grep xyz
RES=$?
check "wit inspect should see the xyz repo added via submodules" [ $RES -eq 0 ]

wit foreach env | grep "xyz"
RES=$?
check "wit foreach should see the xyz repo added via submodules" [ $RES -eq 0 ]

wit -C foo add-dep $xyz_dir
RES=$?
check "wit add-dep should allow foo to depend on xyz which was previously dependend on via submodule" [ $RES -eq 0 ]
git -C foo commit -am "update deps"
wit update-pkg foo
wit update
COUNT=$(wit inspect --tree | grep xyz | wc -l)
check "wit should depend on xyz twice, one by wit, one by submodules" [ $COUNT -eq 2 ]

wit -C baa add-dep $abc_dir
RES=$?
check "wit add-dep shouldn't allow baa to wit-depend on anything as it uses submodules" [ $RES -ne 0 ]





report
finish
