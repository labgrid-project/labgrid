import builtins
import logging
import os
from types import SimpleNamespace

import pytest
from opentelemetry import trace

from labgrid.logging import REDACTED_VALUE
from labgrid.remote import otel

sdk_logs = pytest.importorskip("opentelemetry.sdk._logs")
sdk_export = pytest.importorskip("opentelemetry.sdk._logs.export")
otlp_export = pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc._log_exporter")


@pytest.fixture
def log_pipeline(monkeypatch):
    """Use the real logging bridge and processor without contacting a collector."""
    for name in os.environ:
        if name.startswith("OTEL_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.setattr(trace, "get_tracer_provider", trace.ProxyTracerProvider)
    monkeypatch.setattr(otel, "_enabled", False)
    monkeypatch.setattr(otel, "_log_handler", None)

    root = logging.getLogger()
    logger = logging.getLogger("test-otel-logging")
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "propagate", True)
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "level", logging.INFO)

    exporter = sdk_export.InMemoryLogRecordExporter()
    exporter_calls = []

    def create_exporter(*args, **kwargs):
        exporter_calls.append((args, kwargs))
        return exporter

    monkeypatch.setattr(otlp_export, "OTLPLogExporter", create_exporter)
    providers = []
    provider_type = sdk_logs.LoggerProvider

    def create_provider(*args, **kwargs):
        provider = provider_type(*args, **kwargs)
        providers.append(provider)
        return provider

    monkeypatch.setattr(sdk_logs, "LoggerProvider", create_provider)
    yield SimpleNamespace(
        logger=logger,
        root=root,
        exporter=exporter,
        exporter_calls=exporter_calls,
        providers=providers,
    )
    if otel._log_handler is not None:
        root.removeHandler(otel._log_handler)
        otel._log_handler.close()
    for provider in providers:
        provider.shutdown()


@pytest.mark.parametrize(
    "service_name, override",
    [
        ("labgrid-coordinator", None),
        ("labgrid-exporter", None),
        ("labgrid-coordinator", "custom-coordinator"),
    ],
)
def test_setup_exports_sanitized_logs_once(log_pipeline, monkeypatch, service_name, override):
    original_handlers = log_pipeline.root.handlers[:]
    if override:
        monkeypatch.setenv("OTEL_SERVICE_NAME", override)

    assert otel.setup_otel(service_name)
    assert otel.setup_otel(service_name)
    assert len(log_pipeline.providers) == 1
    assert log_pipeline.root.handlers == original_handlers + [otel._log_handler]
    assert isinstance(otel._log_handler, sdk_logs.LoggingHandler)
    # Preserve the exporter's handling of standard OTLP environment settings.
    assert log_pipeline.exporter_calls == [((), {})]

    log_pipeline.logger.info("api_key=%s", "abc123", extra={"event.name": "request.failed"})
    assert log_pipeline.providers[0].force_flush()
    records = log_pipeline.exporter.get_finished_logs()
    assert len(records) == 1
    assert records[0].log_record.body == f"api_key={REDACTED_VALUE}"
    assert records[0].log_record.attributes["event.name"] == "request.failed"
    assert records[0].resource.attributes["service.name"] == (override or service_name)


def test_logs_exporter_none_keeps_logging_unmodified(log_pipeline, monkeypatch):
    original_handlers = log_pipeline.root.handlers[:]
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "none")
    assert otel.setup_otel("labgrid-coordinator")
    assert log_pipeline.root.handlers == original_handlers
    assert log_pipeline.providers == []
    assert log_pipeline.exporter_calls == []


def test_sdk_disabled_does_not_enable_log_export(log_pipeline, monkeypatch):
    original_handlers = log_pipeline.root.handlers[:]
    monkeypatch.setenv("OTEL_SDK_DISABLED", " TRUE ")
    assert not otel.setup_otel("labgrid-coordinator")
    assert log_pipeline.root.handlers == original_handlers
    assert log_pipeline.providers == []
    assert log_pipeline.exporter_calls == []


@pytest.mark.parametrize(
    "missing",
    ["opentelemetry.sdk._logs", "opentelemetry.exporter.otlp.proto.grpc._log_exporter"],
)
def test_missing_log_dependencies_leave_logging_unmodified(log_pipeline, monkeypatch, missing):
    original_handlers = log_pipeline.root.handlers[:]
    original_import = builtins.__import__

    def without_logging_dependency(name, *args, **kwargs):
        if name.startswith(missing):
            raise ModuleNotFoundError(name=name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_logging_dependency)
    assert not otel.setup_otel("labgrid-coordinator")
    assert log_pipeline.root.handlers == original_handlers
    assert log_pipeline.providers == []
    assert log_pipeline.exporter_calls == []
