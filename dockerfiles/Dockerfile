FROM debian:buster-slim AS labgrid-base

LABEL maintainer="eha@deif.com"

ENV DEBIAN_FRONTEND=noninteractive

COPY ./ /opt/labgrid/

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends python3 python3-dev python3-pip python3-setuptools python3-wheel git build-essential libsnappy-dev ;\
    pip3 install -U pip;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/* ;\
    git clone git://github.com/vishnubob/wait-for-it.git opt/wait-for-it && cd opt/wait-for-it  && git reset --hard 54d1f0bfeb6557adf8a3204455389d0901652242

#
# Client
#
FROM labgrid-base AS labgrid-client
ARG VERSION

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install yq ;\
    pip3 install --no-cache-dir -r requirements.txt ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" python3 setup.py install ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends microcom openssh-client rsync jq qemu-system; \
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
    pip3 install --no-cache-dir -r crossbar-requirements.txt ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" python3 setup.py install

VOLUME /opt/crossbar

EXPOSE 20408

CMD ["crossbar", "start", "--config", "/opt/labgrid/.crossbar/config.yaml"]

#
# ser2net
#
# These have to be built from source to bring in a newer version that has a
# needed bugfix. This can be removed once the images are switched to
# debian:bullseye, as it has a new enough version
#
FROM debian:buster-slim AS ser2net

RUN apt update && \
    apt install --yes --no-install-recommends \
        build-essential \
        cmake \
        python3-dev \
        wget \
        ca-certificates \
        libsctp-dev \
        libssl-dev \
        pkg-config \
        file \
        libyaml-dev \
    && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /src

RUN cd /src && \
    wget https://downloads.sourceforge.net/project/ser2net/ser2net/gensio-2.2.4.tar.gz && \
    tar -xvzf gensio-2.2.4.tar.gz && \
    cd gensio-2.2.4 && \
    mkdir build && \
    cd build && \
    ../configure --prefix=/usr && \
    make && \
    make install && \
    make install DESTDIR=/opt/ser2net

RUN cd /src && \
    wget https://downloads.sourceforge.net/project/ser2net/ser2net/ser2net-4.3.3.tar.gz && \
    tar -xvzf ser2net-4.3.3.tar.gz -C /src && \
    cd /src/ser2net-4.3.3 && \
    mkdir build && \
    cd build && \
    ../configure --prefix=/usr && \
    make && \
    make install DESTDIR=/opt/ser2net

#
# Exporter
#
FROM labgrid-base AS labgrid-exporter
ARG VERSION

COPY dockerfiles/exporter/entrypoint.sh /entrypoint.sh

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --no-cache-dir -r requirements.txt ;\
    SETUPTOOLS_SCM_PRETEND_VERSION="$VERSION" python3 setup.py install ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends \
        libyaml-0-2 \
        libsctp1 \
    ; \
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

COPY --from=ser2net /opt/ser2net /

VOLUME /opt/conf

CMD ["/entrypoint.sh"]
