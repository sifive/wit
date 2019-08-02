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

prereq "off"

wit init --no-fetch-scala myws -a $PWD/foo
cd myws

check "scala should NOT be fetched" [ ! -d "scala" ]

found=$(find . -name "*coursier*" | wc -l)
check "there should NOT be a coursier executable" [ "$found" -eq 0 ]


report
finish
