FROM python:3.7
MAINTAINER eha@deif.com

RUN mkdir -p /opt/labgrid
COPY ./ /opt/labgrid/
RUN cd /opt/labgrid \
 && pip install -r requirements.txt \
 && python setup.py install

RUN apt-get update -q \
 && apt-get install -q -y ser2net \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

VOLUME /opt/conf

COPY docker/exporter/entrypoint.sh /entrypoint.sh
CMD ["/entrypoint.sh"]
