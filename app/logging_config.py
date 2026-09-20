import json
import logging
import logging.config
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Every record includes a UTC timestamp, level, logger name, message and
    source location. Exception tracebacks are embedded under the 'exception'
    key when present.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            'timestamp': datetime.fromtimestamp(
                record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)


def configure_logging() -> None:
    """Configures structured JSON logging for the whole application.

    All modules log through the root logger with a single JSON formatter so
    output is uniform and machine-parseable. The level can be tuned with the
    WHOOGLE_LOG_LEVEL environment variable (default: INFO).
    """
    level = os.getenv('WHOOGLE_LOG_LEVEL', 'INFO').upper()
    if level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        level = 'INFO'

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'app.logging_config.JsonFormatter',
            },
        },
        'handlers': {
            'default': {
                'class': 'logging.StreamHandler',
                'formatter': 'json',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'level': level,
            'handlers': ['default'],
        },
    })
