FROM labgrid-base

RUN set -e ;\
    cd /opt/labgrid ;\
    pip3 install --no-cache-dir -r requirements.txt ;\
    python3 setup.py install ;\
    apt update -q=2 ;\
    apt install -q=2 --yes --no-install-recommends microcom ;\
    apt clean ;\
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
