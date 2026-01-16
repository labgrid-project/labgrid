FROM debian:trixie-slim AS labgrid-base
ARG VERSION=0.0.0

LABEL maintainer="eha@deif.com"

ENV DEBIAN_FRONTEND=noninteractive

COPY ./ /opt/labgrid/

RUN apt update -q=2 && \
    apt install -q=2 --yes --no-install-recommends python3 python3-dev python3-pip python3-setuptools git build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 config --site set global.break-system-packages true && \
    pip3 config --site set global.root-user-action ignore && \
    cd /opt/labgrid && \
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" pip3 install --no-cache-dir .

#
# Client
#
FROM labgrid-base AS labgrid-client
ARG VERSION

RUN pip3 install yq && \
    apt update -q=2  && \
    apt install -q=2 --yes --no-install-recommends microcom openssh-client rsync jq qemu-system qemu-utils && \
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

RUN apt update -q=2 && \
    apt install -q=2 --yes --no-install-recommends ser2net && \
    rm -rf /var/lib/apt/lists/*

VOLUME /opt/conf

CMD ["/entrypoint.sh"]
