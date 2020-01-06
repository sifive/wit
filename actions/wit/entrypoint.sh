#!/usr/bin/env bash

set -euxo pipefail

: ${INPUT_COMMAND:?'The `command` input argument must be set'}

if [[ -n "$INPUT_FORCE_GITHUB_HTTPS" ]]; then
  git config --global url.'https://github.com/'.insteadOf 'git@github.com:'
fi

exec wit "$INPUT_COMMAND" $INPUT_ARGUMENTS
