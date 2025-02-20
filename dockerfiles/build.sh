#!/bin/bash

export DOCKER_BUILDKIT=1
: "${IMAGE_PREFIX:=docker.io/labgrid/}"
: "${IMAGE_TAG:=latest}"

die () {
    local msg
    msg="${1}"

    echo "[fatal] ${msg}" >&2
    exit 1
}

log_info() {
    local msg
    msg="${1}"

    echo "[info] ${msg}"
}

has_docker() {
    command -v docker >/dev/null 2>&1
}

has_podman() {
    command -v podman >/dev/null 2>&1
}

has_buildx() {
    local docker_cmd
    docker_cmd="${1}"

    "${docker_cmd}" buildx version >/dev/null 2>&1
}

get_docker_cmd() {
    local docker_cmd
    docker_cmd="${1}"

    if [ -n "${docker_cmd}" ]; then
        echo "${docker_cmd}"
        return
    fi

    if has_docker; then
        echo "docker"
    else
        echo "podman"
    fi
}

perform_regular_build() {
    local docker_cmd script_dir version
    docker_cmd="${1}"
    script_dir="${2}"
    version="${3}"
    extra_args=("${@:4}")

    log_info "building for native platform only."

    for t in client exporter coordinator; do
        "${docker_cmd}" build --build-arg VERSION="${version}" \
            --target labgrid-${t} -t "${IMAGE_PREFIX}${t}:${IMAGE_TAG}" -f "${script_dir}/Dockerfile" \
            "${extra_args[@]}" .
    done
}

perform_docker_buildx_build() {
    local docker_cmd script_dir version
    docker_cmd="${1}"
    script_dir="${2}"
    version="${3}"
    extra_args=("${@:4}")

    for t in client exporter coordinator; do
        "${docker_cmd}" buildx build --build-arg VERSION="${version}" \
            --target labgrid-${t} -t "${IMAGE_PREFIX}${t}:${IMAGE_TAG}" -f "${script_dir}/Dockerfile" \
            "${extra_args[@]}" .
    done
}

main() {
    local script_dir version

    if ! has_docker && ! has_podman; then
        die "Neither docker nor podman could be found."
    fi

    script_dir="$(dirname "$(realpath "${BASH_SOURCE:-$0}")")"
    version="$(python -m setuptools_scm)"
    docker_cmd="$(get_docker_cmd "${DOCKER}")"

    cd "${script_dir}/.." || die "Could not cd into repo root dir"

    if has_buildx "${docker_cmd}"; then
        perform_docker_buildx_build "${docker_cmd}" "${script_dir}" "${version}" "${@}"
    else
        perform_regular_build "${docker_cmd}" "${script_dir}" "${version}" "${@}"
    fi
}

main "${@}"
