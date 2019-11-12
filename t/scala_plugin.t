#!/bin/sh

. $(dirname $0)/test_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'

cat << EOF | jq . > foo/ivydependencies.json
{
    "foo": {
      "scalaVersion": "2.12.8",
      "dependencies": [
          "org.json4s::json4s-native:3.6.1",
          "org.antlr:antlr4:4.7.2"
      ]
    }
}
EOF

git -C foo add -A
git -C foo commit -m "add ivydependencies.json"

foo_commit=$(git -C foo rev-parse HEAD)
prereq "off"

# Now create a workspace
wit init myws -a $PWD/foo

cd myws

jar="json4s-native_2.12-3.6.1.jar"
found=$(find ivycache -name "$jar")
check "We should find $jar" [ ! -z "$found" ]

coursier_bin="scala/coursier"
check "$coursier_bin should exist" [ -f "$coursier_bin" ]

# This one is implicit in the Scala Version
scala_jar="scala-compiler-2.12.8.jar"
found_scala=$(find ivycache -name "$scala_jar")
check "We should also find Scala" [ ! -z $found_scala ]

# Because we fetch Scala Version together with the dependencies, we get Scala
# 2.12.8 but not 2.12.6 (which is the one json4s directly depends on)
bad_scala_jar="scala-library-2.12.6.jar"
not_found_scala=$(find ivycache -name "$bad_scala_jar")
check "We should not find the wrong Scala" [ -z $not_found_scala ]

# Find compiler bridge excluding 'target' directory where dependencies are being kept
compiler_bridge=$(find scala/bloop_home -type d -name target -prune -o -name '*scala-compiler-bridge*.jar' -print)
check "We should find the compiler bridge" [ ! -z $compiler_bridge ]

report
finish
