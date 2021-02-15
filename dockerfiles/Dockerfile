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

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --no-cache-dir -r requirements.txt ;\
    python3 setup.py install ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends microcom openssh-client sshpass rsync; \
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]

#
# Coordinator
#
FROM labgrid-base AS labgrid-coordinator

ENV CROSSBAR_DIR=/opt/crossbar

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --no-cache-dir -r crossbar-requirements.txt ;\
    python3 setup.py install

VOLUME /opt/crossbar

EXPOSE 20408

CMD ["crossbar", "start", "--config", "/opt/labgrid/.crossbar/config.yaml"]

#
# Exporter
#
FROM labgrid-base AS labgrid-exporter

COPY dockerfiles/exporter/entrypoint.sh /entrypoint.sh

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --no-cache-dir -r requirements.txt ;\
    python3 setup.py install ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends ser2net ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

VOLUME /opt/conf

CMD ["/entrypoint.sh"]
