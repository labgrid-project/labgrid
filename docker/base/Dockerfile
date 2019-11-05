FROM debian:buster-slim

LABEL maintainer="eha@deif.com"

ENV DEBIAN_FRONTEND=noninteractive

COPY ./ /opt/labgrid/

RUN set -e ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends python3 python3-dev python3-pip python3-setuptools python3-wheel git build-essential libsnappy-dev ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*
