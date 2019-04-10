#!/bin/sh

. $(dirname $0)/regress_util.sh

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
found=$(find . -name "$jar")
check "We should find $jar" [ ! -z "$found" ]

bloop_bin="scala/bloop"
check "$bloop_bin should exist" [ -f "$bloop_bin" ]

coursier_bin="scala/blp-coursier"
check "$coursier_bin should exist" [ -f "$coursier_bin" ]

# This one is implicit in the Scala Version
scala_jar="scala-compiler-2.12.8.jar"
found_scala=$(find . -name "$scala_jar")
check "We should also find Scala" [ ! -z $found_scala ]

report
finish
