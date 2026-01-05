#!/usr/bin/env bash
set -x
ARCH=$(uname -m)

IMAGE_NAME_PREFIX="frappe-manager-local"

if [[ "${ARCH}" == "x86_64" ]]; then
    ARCH="amd64"
elif [[ "${ARCH}" == "aarch64" ]]; then
    ARCH="arm64"
fi

PYTHON_VERSIONS="${PYTHON_VERSIONS:-3.12.0}"
PYENV_GIT_VERSION="${PYENV_GIT_VERSION:-2.6.17}"
NVM_VERSION="${NVM_VERSION:-0.40.3}"
NODE_VERSIONS="${NODE_VERSIONS:-22.18.0}"
PREBAKE_APPS="${PREBAKE_APPS:-erpnext:version-15,hrms:version-15}"
PREBAKE_FRAPPE_BRANCH="${PREBAKE_FRAPPE_BRANCH:-version-15}"

NO_CACHE="${NO_CACHE:-false}"
if [[ "$1" == "--no-cache" ]]; then
    NO_CACHE=true
    shift
fi

images='frappe'

for image in ${images}; do
    if ! IMAGE_TAG=$(jq -rc ".${image}" images-tag.json); then
        echo "Warning: Failed to read image tag for '${image}' from images-tag.json" >&2
        continue
    fi

    if [[ "${IMAGE_TAG:-}" ]]; then
        CONTEXT_DIR="${image}/."

        PREBAKE_IMAGE_NAME="${IMAGE_NAME_PREFIX}-prebake"
        PREBAKE_IMAGE_NAME_WITH_TAG="${PREBAKE_IMAGE_NAME}:${IMAGE_TAG}"
        
        echo "Building ${PREBAKE_IMAGE_NAME_WITH_TAG}"
        echo "Build arguments:"
        echo "  PYTHON_VERSIONS=${PYTHON_VERSIONS}"
        echo "  PYENV_GIT_VERSION=${PYENV_GIT_VERSION}"
        echo "  NVM_VERSION=${NVM_VERSION}"
        echo "  NODE_VERSIONS=${NODE_VERSIONS}"
        echo "  PREBAKE_APPS=${PREBAKE_APPS}"
        echo "  PREBAKE_FRAPPE_BRANCH=${PREBAKE_FRAPPE_BRANCH}"

        NO_CACHE_FLAG=""
        if [[ "${NO_CACHE}" == "true" ]]; then
            NO_CACHE_FLAG="--no-cache"
            echo "  NO_CACHE=true"
        fi

        docker build \
          ${NO_CACHE_FLAG} \
          --platform linux/${ARCH} \
          --build-arg PYTHON_VERSIONS="${PYTHON_VERSIONS}" \
          --build-arg PYENV_GIT_VERSION="${PYENV_GIT_VERSION}" \
          --build-arg NVM_VERSION="${NVM_VERSION}" \
          --build-arg NODE_VERSIONS="${NODE_VERSIONS}" \
          --build-arg PREBAKE_APPS="${PREBAKE_APPS}" \
          --build-arg PREBAKE_FRAPPE_BRANCH="${PREBAKE_FRAPPE_BRANCH}" \
          --target prebake_image \
          -t "${PREBAKE_IMAGE_NAME_WITH_TAG}" \
          "${CONTEXT_DIR}" \

        IMAGE_NAME="${IMAGE_NAME_PREFIX}-${image}"
        IMAGE_NAME_WITH_TAG="${IMAGE_NAME}:${IMAGE_TAG}"

        echo "Building ${IMAGE_NAME_WITH_TAG}"

        docker build \
          ${NO_CACHE_FLAG} \
          --platform linux/${ARCH} \
          --build-arg PYTHON_VERSIONS="${PYTHON_VERSIONS}" \
          --build-arg PYENV_GIT_VERSION="${PYENV_GIT_VERSION}" \
          --build-arg NVM_VERSION="${NVM_VERSION}" \
          --build-arg NODE_VERSIONS="${NODE_VERSIONS}" \
          --build-arg PREBAKE_APPS="${PREBAKE_APPS}" \
          --build-arg PREBAKE_FRAPPE_BRANCH="${PREBAKE_FRAPPE_BRANCH}" \
          --target fm_image \
          -t "${IMAGE_NAME_WITH_TAG}" \
          "${CONTEXT_DIR}"
    fi
done
