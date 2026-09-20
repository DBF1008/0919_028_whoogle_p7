"""Graceful shutdown support for the Waitress server.

Installs SIGTERM/SIGINT handlers, tracks in-flight requests through a small
WSGI middleware, and on shutdown stops accepting new connections, waits for
in-flight requests to finish (bounded by a timeout), closes shared HTTP
clients and force-exits if the grace period elapses.
"""

import logging
import os
import signal
import threading
import time

from app.services.provider import close_all_clients

logger = logging.getLogger(__name__)


def _shutdown_timeout() -> float:
    try:
        return max(0.0, float(os.environ.get('WHOOGLE_SHUTDOWN_TIMEOUT',
                                             '30')))
    except ValueError:
        return 30.0


class RequestTracker:
    """WSGI middleware counting in-flight (non-health) requests."""

    def __init__(self, wsgi_app, graceful):
        self._wsgi_app = wsgi_app
        self._graceful = graceful

    def __call__(self, environ, start_response):
        if self._graceful.is_health_check(environ):
            return self._wsgi_app(environ, start_response)

        self._graceful.request_started()
        graceful = self._graceful

        class _Response:
            def __init__(self, response):
                self._response = response
                self._closed = False

            def __iter__(self):
                try:
                    for chunk in self._response:
                        yield chunk
                finally:
                    self.close()

            def close(self):
                if not self._closed:
                    self._closed = True
                    graceful.request_finished()
                if hasattr(self._response, 'close'):
                    self._response.close()

        return _Response(self._wsgi_app(environ, start_response))


class GracefulShutdown:
    def __init__(self):
        self._active_requests = 0
        self._condition = threading.Condition()
        self._shutting_down = threading.Event()
        self._installed = False
        self._lock = threading.Lock()

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down.is_set()

    @property
    def active_requests(self) -> int:
        return self._active_requests

    def is_health_check(self, environ) -> bool:
        path = environ.get('PATH_INFO', '')
        prefix = os.environ.get('WHOOGLE_URL_PREFIX', '')
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        return path in ('/healthz', '/healthz/')

    def request_started(self):
        with self._condition:
            self._active_requests += 1

    def request_finished(self):
        with self._condition:
            self._active_requests -= 1
            if self._active_requests <= 0:
                self._condition.notify_all()

    def attach(self):
        """Idempotently install signal handlers (main thread only)."""
        with self._lock:
            if self._installed:
                return
            if threading.current_thread() is not threading.main_thread():
                return
            self._install_signals()
            self._installed = True

    def _install_signals(self):
        for signame in ('SIGTERM', 'SIGINT'):
            sig = getattr(signal, signame, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, self._handle_signal)
            except (ValueError, OSError):
                # Signal handling unavailable in this context
                continue

    def _handle_signal(self, signum, frame):
        # A second signal forces an immediate exit
        if self._shutting_down.is_set():
            os._exit(128 + int(signum))
        self._shutting_down.set()

    def wait_for_requests(self, timeout):
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._active_requests > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
        return True

    def serve(self, create_server):
        """Run a Waitress server factory with graceful shutdown.

        Args:
            create_server: zero-arg callable returning a started Waitress
                server instance.
        """
        self.attach()
        server = create_server()
        server_thread = threading.Thread(target=server.run,
                                         name='waitress-server',
                                         daemon=True)
        server_thread.start()

        while not self._shutting_down.is_set():
            time.sleep(0.2)

        sig_timeout = _shutdown_timeout()
        logger.info('shutdown initiated, waiting for in-flight requests',
                    extra={'active_requests': self.active_requests,
                           'shutdown_timeout': sig_timeout})

        # Stop accepting new connections
        try:
            server.close()
        except Exception:
            logger.exception('error while closing listening socket')

        completed = self.wait_for_requests(sig_timeout)
        if not completed:
            logger.warning('grace period elapsed, forcing shutdown',
                           extra={'active_requests': self.active_requests})

        for channel in list(getattr(server, 'active_channels', {}).values()):
            try:
                channel.close()
            except Exception:
                pass

        server_thread.join(timeout=5)
        if server_thread.is_alive():
            logger.warning('server did not stop in time, exiting process')

        try:
            close_all_clients()
        except Exception:
            logger.exception('error while closing shared HTTP clients')

        if not completed:
            logging.shutdown()
            os._exit(1)


graceful = GracefulShutdown()
