import json
import logging
import sys

from app.logging_config import JsonFormatter, configure_logging


def _make_record(msg='hello %s', args=('world',), exc_info=None):
    return logging.LogRecord(
        'test.logger', logging.INFO, 'path.py', 10, msg, args, exc_info)


def test_json_formatter_fields():
    output = json.loads(JsonFormatter().format(_make_record()))
    assert output['level'] == 'INFO'
    assert output['logger'] == 'test.logger'
    assert output['message'] == 'hello world'
    assert output['module'] == 'path'
    assert output['line'] == 10
    assert 'timestamp' in output


def test_json_formatter_exception():
    try:
        raise ValueError('boom')
    except ValueError:
        record = _make_record(msg='failed', args=(), exc_info=sys.exc_info())
    output = json.loads(JsonFormatter().format(record))
    assert 'ValueError: boom' in output['exception']


def test_configure_logging_level(monkeypatch):
    monkeypatch.setenv('WHOOGLE_LOG_LEVEL', 'DEBUG')
    configure_logging()
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert any(isinstance(h.formatter, JsonFormatter)
               for h in root.handlers)


def test_configure_logging_invalid_level(monkeypatch):
    monkeypatch.setenv('WHOOGLE_LOG_LEVEL', 'not-a-level')
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_output_json(monkeypatch, caplog):
    monkeypatch.setenv('WHOOGLE_LOG_LEVEL', 'INFO')
    configure_logging()
    logger = logging.getLogger('whoogle.test')
    with caplog.at_level(logging.INFO, logger='whoogle.test'):
        logger.info('structured test message')
    assert 'structured test message' in caplog.text
