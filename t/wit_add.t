#!/bin/sh

. $(dirname $0)/regress_util.sh

hash=e8e3572be10994a140f0086abc7a0533272832eb
echo "Verify that we can create a workspace with no initial repo"
wit init myws -a ${wit_repo}::${hash}

cd myws
wit_manifest_hash=$(jq -r '.[] | select(.name=="wit") | .commit' wit-manifest.json)
check "Wit manifest contains requested hash" [ "$wit_manifest_hash" = "$hash" ]

wit update
git_repo_hash=$(git --git-dir=wit/.git rev-parse HEAD)
check "Updated wit repo is at requested hash" [ "$git_repo_hash" = "$hash" ]

report
finish
