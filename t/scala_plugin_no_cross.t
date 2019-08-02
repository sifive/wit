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

cat << EOF | jq . > foo/wit-manifest.json
[
    {
        "commit": "9246f3400b8fab6eccc828981026c9947d4a1b0c",
        "name": "wit-scala-plugin",
        "source": "https://github.com/sifive/wit-scala-plugin"
    }
]
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
check "We should *not* find $jar2" [ -z "$found2" ]

report
finish
