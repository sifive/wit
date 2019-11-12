#!/bin/sh

. $(dirname $0)/test_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'

cat << EOF | jq . > foo/ivydependencies.json
{
    "foo": {
      "scalaVersion": "2.12.8",
      "crossScalaVersions": ["2.11.12"],
      "dependencies": [
          "org.json4s::json4s-native:3.6.1"
      ]
    }
}
EOF

git -C foo add -A
git -C foo commit -m "add ivydependencies.json"

# Note we intentionally have a project name collision below ("foo"),
# This should have no effect on wit
make_repo 'bar'

cat << EOF | jq . > bar/ivydependencies.json
{
    "foo": {
      "scalaVersion": "2.11.12"
    }
}
EOF

git -C bar add -A
git -C bar commit -m "add ivydependencies.json"

prereq "off"

# Now create a workspace
wit init myws -a $PWD/foo -a $PWD/bar

cd myws
wit fetch-scala

check "wit fetch-scala should succeed" [ $? -eq 0 ]

jar="json4s-native_2.12-3.6.1.jar"
found=$(find ivycache -name "$jar")
check "We should find $jar" [ ! -z "$found" ]

jar2="json4s-native_2.11-3.6.1.jar"
found2=$(find ivycache -name "$jar2")
check "We should find $jar2" [ ! -z "$found2" ]

# This one is implicit in the Scala Version
scala_jar="scala-compiler-2.12.8.jar"
found_scala=$(find ivycache -name "$scala_jar")
check "We should also find Scala 2.12.8" [ ! -z $found_scala ]

scala_jar2="scala-compiler-2.11.12.jar"
found_scala2=$(find ivycache -name "$scala_jar2")
check "We should also find Scala 2.11.12" [ ! -z $found_scala2 ]

report
finish
