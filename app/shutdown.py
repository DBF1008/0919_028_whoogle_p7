import logging
import os
import signal
import threading

from app.services.provider import close_all_clients

logger = logging.getLogger(__name__)

# Signals handled for graceful shutdown
SHUTDOWN_SIGNALS = (signal.SIGTERM, signal.SIGINT)

# Default maximum time (seconds) to wait for in-flight requests to finish
# before forcing the process to exit
DEFAULT_SHUTDOWN_TIMEOUT = 30.0


class ShutdownManager:
    """Coordinates graceful shutdown of the application.

    Tracks in-flight requests and, when a shutdown signal is received:
      1. Stops the HTTP server from accepting new connections
      2. Waits for in-flight requests to complete (up to a timeout)
      3. Closes all shared HTTP clients
      4. Exits the process (forced if the timeout is exceeded)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight = 0
        self._drained = threading.Event()
        self._drained.set()
        self._shutting_down = False
        self._servers = []
        self._handlers_installed = False

    @property
    def shutdown_timeout(self) -> float:
        try:
            return float(os.getenv(
                'WHOOGLE_SHUTDOWN_TIMEOUT', DEFAULT_SHUTDOWN_TIMEOUT))
        except (TypeError, ValueError):
            return DEFAULT_SHUTDOWN_TIMEOUT

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def in_flight_count(self) -> int:
        with self._lock:
            return self._in_flight

    def init_app(self, app) -> None:
        """Registers in-flight request tracking on a Flask app."""
        @app.before_request
        def _track_request_start():
            self.request_started()

        @app.teardown_request
        def _track_request_end(exception=None):
            self.request_finished()

    def request_started(self) -> None:
        with self._lock:
            self._in_flight += 1
            self._drained.clear()

    def request_finished(self) -> None:
        with self._lock:
            if self._in_flight > 0:
                self._in_flight -= 1
            if self._in_flight == 0:
                self._drained.set()

    def register_server(self, server) -> None:
        """Registers an HTTP server to stop on shutdown."""
        self._servers.append(server)

    def install_signal_handlers(self) -> None:
        """Installs SIGTERM/SIGINT handlers (main thread only, idempotent)."""
        if self._handlers_installed:
            return
        if threading.current_thread() is not threading.main_thread():
            return
        for sig in SHUTDOWN_SIGNALS:
            signal.signal(sig, self._handle_signal)
        self._handlers_installed = True

    def _handle_signal(self, signum, frame) -> None:
        if self._shutting_down:
            logger.warning(
                'Received signal %s during shutdown, forcing exit', signum)
            os._exit(1)
        self.initiate_shutdown(signum)

    def initiate_shutdown(self, signum=None) -> None:
        """Performs the graceful shutdown sequence."""
        if self._shutting_down:
            return
        self._shutting_down = True
        timeout = self.shutdown_timeout
        logger.info(
            'Shutdown requested (signal=%s), draining up to %ss in-flight '
            'requests', signum, timeout)

        # Stop accepting new connections
        for server in self._servers:
            try:
                server.close()
            except Exception:
                logger.exception('Error closing server socket')

        # Wait for in-flight requests to finish
        if not self._drained.wait(timeout):
            logger.warning(
                'Shutdown timeout (%ss) exceeded with %s request(s) still '
                'in flight, forcing exit', timeout, self.in_flight_count)
        else:
            logger.info('All in-flight requests completed')

        # Release shared resources
        try:
            close_all_clients()
        except Exception:
            logger.exception('Error closing HTTP clients')

        logger.info('Shutdown complete')
        os._exit(0)


shutdown_manager = ShutdownManager()
