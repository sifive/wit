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
          "org.json4s::json4s-native:3.6.1"
      ]
    }
}
EOF

git -C foo add -A
make_commit foo "add ivydependencies.json"

prereq "off"

wit init --no-fetch-scala myws -a $PWD/foo
cd myws

check "scala should NOT be fetched" [ ! -d "scala" ]

found=$(find . -name "*coursier*" | wc -l)
check "there should NOT be a coursier executable" [ "$found" -eq 0 ]


report
finish
