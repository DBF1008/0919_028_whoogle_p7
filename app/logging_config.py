"""Centralized logging configuration.

Emits structured JSON log lines by default (one JSON object per line on
stderr). Set WHOOGLE_LOG_FORMAT=text to fall back to human-readable lines.
All application modules should log through ``logging.getLogger(__name__)``.
"""

import datetime
import json
import logging
import os
import sys

_RESERVED_ATTRS = set(logging.makeLogRecord({}).__dict__.keys()) | {
    'message',
    'asctime',
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'ts': datetime.datetime.fromtimestamp(
                record.created,
                tz=datetime.timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key in payload:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = str(value)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging():
    level_name = os.environ.get('WHOOGLE_LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.environ.get('WHOOGLE_LOG_FORMAT', 'json').lower()

    handler = logging.StreamHandler(sys.stderr)
    if fmt == 'json':
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s [%(name)s] %(message)s'))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Keep library loggers flowing through the root handler
    for name in ('app', 'waitress', 'werkzeug', 'httpx', 'httpcore',
                 'urllib3', 'stem'):
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(level)
        lib_logger.propagate = True

    logging.captureWarnings(True)
