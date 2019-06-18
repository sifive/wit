#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'

cat << EOF | jq . > foo/ivydependencies.json
{
    "foo": {
      "scalaVersion": "2.12.8"
    }
}
EOF

git -C foo add -A
git -C foo commit -m "add ivydependencies.json"

foo_commit=$(git -C foo rev-parse HEAD)
coursier_cache=$PWD/coursier_cache

prereq "off"

COURSIER_CACHE=$coursier_cache wit init myws -a $PWD/foo

cd myws

local_cache=$PWD/ivycache



#jar="json4s-native_2.12-3.6.1.jar"
#found=$(find . -name "$jar")
#check "We should find $jar" [ ! -z "$found" ]
#
#coursier_bin="scala/coursier"
#check "$coursier_bin should exist" [ -f "$coursier_bin" ]
#
## This one is implicit in the Scala Version
#scala_jar="scala-compiler-2.12.8.jar"
#found_scala=$(find . -name "$scala_jar")
#check "We should also find Scala" [ ! -z $found_scala ]
#
## Because we fetch Scala Version together with the dependencies, we get Scala
## 2.12.8 but not 2.12.6 (which is the one json4s directly depends on)
#bad_scala_jar="scala-library-2.12.6.jar"
#not_found_scala=$(find . -name "$bad_scala_jar")
#check "We should not find the wrong Scala" [ -z $not_found_scala ]

report
finish
