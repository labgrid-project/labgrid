FROM python:3.6
MAINTAINER krev@triax.com

# Tools
RUN apt-get update && \
    apt-get install -y ser2net && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/labgrid

# Ensure that labgrid is build from current dir
COPY ./ ./
RUN pip install crossbar
RUN pip install -e /opt/labgrid
RUN git clone https://github.com/vishnubob/wait-for-it.git /opt/wait-for-it
