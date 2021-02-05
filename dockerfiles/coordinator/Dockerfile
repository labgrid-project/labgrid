FROM labgrid-base

ENV CROSSBAR_DIR=/opt/crossbar

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --no-cache-dir -r crossbar-requirements.txt ;\
    python3 setup.py install

VOLUME /opt/crossbar

EXPOSE 20408

CMD ["crossbar", "start", "--config", "/opt/labgrid/.crossbar/config.yaml"]
