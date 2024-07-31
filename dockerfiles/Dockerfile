FROM debian:bookworm-slim AS labgrid-base
ARG VERSION

LABEL maintainer="eha@deif.com"

ENV DEBIAN_FRONTEND=noninteractive

COPY ./ /opt/labgrid/

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends python3 python3-dev python3-pip python3-setuptools git build-essential libsnappy-dev ;\
    pip3 install --break-system-packages -U pip;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/* ;\
    cd /opt/labgrid ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" pip3 install --break-system-packages --no-cache-dir .

#
# Client
#
FROM labgrid-base AS labgrid-client
ARG VERSION

RUN set -e ;\
    pip3 install --break-system-packages yq ;\
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

VOLUME /opt/coordinator

EXPOSE 20408

WORKDIR /opt/coordinator

CMD ["/usr/local/bin/labgrid-coordinator"]

#
# Exporter
#
FROM labgrid-base AS labgrid-exporter
ARG VERSION

COPY dockerfiles/exporter/entrypoint.sh /entrypoint.sh

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends ser2net ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

VOLUME /opt/conf

CMD ["/entrypoint.sh"]
