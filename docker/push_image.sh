#!/bin/bash
set -euxo pipefail

docker login -u "$DOCKER_USERNAME" -p "$DOCKER_PASSWORD"
docker push "$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG"
