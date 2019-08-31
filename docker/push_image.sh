#!/bin/bash
set -euxo pipefail

docker login -u "$DOCKERHUB_USERNAME" -p "$DOCKERHUB_PASSWORD"
docker push "$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG"
