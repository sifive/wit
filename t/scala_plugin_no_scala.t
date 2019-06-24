#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'

cat << EOF | jq . > foo/ivydependencies.json
{
    "foo": {
      "dependencies": [
          "org.antlr:antlr4:4.7.2"
      ]
    }
}
EOF

git -C foo add -A
git -C foo commit -m "add ivydependencies.json"

prereq "off"

# Now create a workspace
wit init myws -a $PWD/foo

cd myws
wit fetch-scala

check "wit fetch-scala should succeed" [ $? -eq 0 ]

jar="antlr4-4.7.2.jar"
found=$(find ivycache -name "$jar")
check "We should find $jar" [ ! -z "$found" ]

report
finish
