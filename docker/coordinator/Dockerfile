FROM python:3.7
MAINTAINER eha@deif.com

RUN mkdir -p /opt/labgrid
COPY ./ /opt/labgrid/
RUN cd /opt/labgrid \
 && pip install -r crossbar-requirements.txt \
 && python setup.py install

VOLUME /opt/crossbar
EXPOSE 20408

ENV CROSSBAR_DIR=/opt/crossbar
CMD ["crossbar", "start", "--config", "/opt/labgrid/.crossbar/config.yaml"]
