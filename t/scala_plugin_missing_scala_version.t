#!/bin/sh

. $(dirname $0)/regress_util.sh

prereq "on"

# Set up repo foo
make_repo 'foo'

cat << EOF | jq . > foo/ivydependencies.json
{
    "foo": {
      "dependencies": [
          "org.scalamacros:::paradise:2.1.0"
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

foo_commit=$(git -C foo rev-parse HEAD)
prereq "off"

# Now create a workspace
wit init myws -a $PWD/foo

cd myws
wit fetch-scala

check "wit fetch-scala should error if we have Scala dependencies with no scalaVersion" [ $? -ne 0 ]

report
finish
