FROM labgrid-base

COPY docker/exporter/entrypoint.sh /entrypoint.sh

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
