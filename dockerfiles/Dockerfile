FROM debian:bookworm-slim AS labgrid-base

LABEL maintainer="eha@deif.com"

ENV DEBIAN_FRONTEND=noninteractive

COPY ./ /opt/labgrid/

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends python3 python3-dev python3-pip python3-setuptools git build-essential libsnappy-dev ;\
    pip3 install --break-system-packages -U pip;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

#
# Client
#
FROM labgrid-base AS labgrid-client
ARG VERSION

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --break-system-packages yq ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" pip3 install --break-system-packages --no-cache-dir . ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends microcom openssh-client rsync jq qemu-system qemu-utils ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]

#
# Coordinator
#
FROM labgrid-base AS labgrid-coordinator
ARG VERSION

ENV CROSSBAR_DIR=/opt/crossbar

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --break-system-packages virtualenv ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" pip3 install --break-system-packages --no-cache-dir . ;\
    virtualenv -p python3 crossbar-venv ;\
    crossbar-venv/bin/pip3 install --break-system-packages -r crossbar-requirements.txt ;\
    sed -i "s#^  executable: .*\$#  executable: python3#" .crossbar/config-anonymous.yaml

VOLUME /opt/crossbar

EXPOSE 20408

CMD ["/opt/labgrid/crossbar-venv/bin/crossbar", "start", "--config", "/opt/labgrid/.crossbar/config-anonymous.yaml"]

#
# Exporter
#
FROM labgrid-base AS labgrid-exporter
ARG VERSION

COPY dockerfiles/exporter/entrypoint.sh /entrypoint.sh

RUN set -e ;\
    cd /opt/labgrid ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" pip3 install --break-system-packages --no-cache-dir . ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends ser2net ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

VOLUME /opt/conf

CMD ["/entrypoint.sh"]
