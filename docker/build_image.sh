#!/bin/bash
set -euxo pipefail

docker build --file=docker/wit.Dockerfile --tag="$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG" .
