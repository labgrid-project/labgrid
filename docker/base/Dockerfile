FROM debian:buster-slim

LABEL maintainer="eha@deif.com"

ENV DEBIAN_FRONTEND=noninteractive

COPY ./ /opt/labgrid/

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends python3 python3-dev python3-pip python3-setuptools python3-wheel git build-essential libsnappy-dev ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/* ;\
    git clone git://github.com/vishnubob/wait-for-it.git opt/wait-for-it && cd opt/wait-for-it  && git reset --hard 54d1f0bfeb6557adf8a3204455389d0901652242
