#!/usr/bin/env bash

set -euxo pipefail

: ${INPUT_COMMAND:?'The `command` input argument must be set'}

if [[ -n "$INPUT_FORCE_GITHUB_HTTPS" ]]; then
  # Don't echo the token
  set +x
  if [[ -n "$INPUT_HTTP_AUTH_TOKEN" ]]; then
    git config --global url."https://${INPUT_HTTP_AUTH_USERNAME}:${INPUT_HTTP_AUTH_TOKEN}@github.com/".insteadOf 'git@github.com:'
  else
    git config --global url.'https://github.com/'.insteadOf 'git@github.com:'
  fi
  set -x
fi

exec wit "$INPUT_COMMAND" $INPUT_ARGUMENTS
