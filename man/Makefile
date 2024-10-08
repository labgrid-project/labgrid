PAGES := labgrid-client.1 labgrid-coordinator.1 labgrid-exporter.1 labgrid-device-config.5 labgrid-pytest.7 labgrid-suggest.1
COMPRESSED := labgrid-client.1.gz labgrid-coordinator.1.gz labgrid-exporter.1.gz labgrid-device-config.5.gz labgrid-pytest.7.gz labgrid-suggest.1.gz

%.1 %.5 %.7: %.rst
	rst2man $< >$@.tmp
	mv -f $@.tmp $@

%.gz : %
	gzip $<


all: $(PAGES)

compressed: $(COMPRESSED)

.PHONY: clean
clean:
	rm -f $(COMPRESSED) $(PAGES)
