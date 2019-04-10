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
          "org.scalamacros:::paradise:2.1.0"
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
wit fetch-scala

check "wit fetch-scala should succeed" [ $? -eq 0 ]

jar="paradise_2.12.8-2.1.0.jar"
found=$(find . -name "$jar")
check "We should find $jar" [ ! -z "$found" ]

report
finish
