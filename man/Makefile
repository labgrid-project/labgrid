PAGES := labgrid-client.1 labgrid-exporter.1 labgrid-device-config.1 labgrid-pytest.1
COMPRESSED := labgrid-client.1.gz labgrid-exporter.1.gz labgrid-device-config.1.gz labgrid-pytest.1.gz

%.1: %.rst
	rst2man.py $< > $@

%.1.gz : %.1
	gzip $<


all: $(PAGES)

compressed: $(COMPRESSED)

.PHONY: clean
clean:
	rm -f $(COMPRESSED) $(PAGES)
