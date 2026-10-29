import logging
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

from labgrid.logging import (
    REDACTED_VALUE,
    MasqueradingFormatter,
    MasqueradingLogExporter,
)


def test_otel_log_exporter_masquerades_attributes():
    log_data = SimpleNamespace(
        log_record=SimpleNamespace(
            body="request with Bearer abcdef012345",
            attributes={
                "password": "correct-horse-battery-staple",
                "password2": "correct horse battery staple",
                "message": ("JWT eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.signature"),
                "request": {"access_token": "token-123"},
                "Authorization": "Bearer mF_9.B5f-4.1JqM",
                "client_secret": "sk_live_51N4x7a9Qp2Lm8Vz",
                "userCredential": "service-account:correct-horse-battery-staple",
                "session_token": ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEyMyJ9.signature"),
                "token": "reservation-token",
                "compound_struct_value": "{Password:secret, Token:token}",
                "password_parantheses": '"some password"',
                "pass": "should be redacted as well",
                "headers": ["Authorization: Bearer mF_9.B5f-4.1JqM"],
                "": "Bearer secret",
                "bearer": "Bearer mF_9.B5f-4.1JqM",
                "body_text": "correct horse battery staple",
                "body": b'{"username":"alice","password":"correct-horse-battery-staple"}',
            },
        )
    )

    exporter = Mock()
    MasqueradingLogExporter(exporter).export((log_data,))

    exporter.export.assert_called_once_with((log_data,))

    assert log_data.log_record.body == f"request with {REDACTED_VALUE}"
    got = log_data.log_record.attributes
    assert got["password"] == REDACTED_VALUE
    assert got["password2"] == REDACTED_VALUE
    assert got["headers"][0] == f"Authorization: {REDACTED_VALUE}"
    assert got["message"] == f"JWT {REDACTED_VALUE}"
    assert got["request"]["access_token"] == REDACTED_VALUE
    assert got["Authorization"] == REDACTED_VALUE
    assert got["client_secret"] == REDACTED_VALUE
    assert got["userCredential"] == REDACTED_VALUE
    assert got["session_token"] == REDACTED_VALUE
    assert got["token"] == REDACTED_VALUE
    assert got["compound_struct_value"] == (f"{{Password:{REDACTED_VALUE}, Token:{REDACTED_VALUE}}}")
    assert got["password_parantheses"] == REDACTED_VALUE
    assert got["pass"] == REDACTED_VALUE
    assert got["bearer"] == REDACTED_VALUE
    assert got[""] == REDACTED_VALUE
    assert got["body_text"] == "correct horse battery staple"
    assert got["body"] == (b'{"username":"alice","password":"[REDACTED]"}')


def test_stdout_formatter_masquerades_extra_fields():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        MasqueradingFormatter(logging.Formatter("%(message)s api_key=%(api_key)s"))
    )
    logger = logging.getLogger("test-masquerading-formatter")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        logger.info("request failed", extra={"api_key": "abc123"})
    finally:
        logger.removeHandler(handler)

    assert stream.getvalue().strip() == f"request failed api_key={REDACTED_VALUE}"


def test_stdout_formatter_masquerades_positional_arguments():
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "api_key=%s",
        ("abc123",),
        None,
    )

    message = MasqueradingFormatter(logging.Formatter("%(message)s")).format(record)

    assert message == f"api_key={REDACTED_VALUE}"
