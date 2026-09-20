import threading
import time

import pytest

from app.shutdown import ShutdownManager


class FakeServer:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def no_exit(monkeypatch):
    """Prevents the shutdown sequence from actually exiting the process."""
    exits = []
    monkeypatch.setattr('app.shutdown.os._exit', exits.append)
    monkeypatch.setattr('app.shutdown.close_all_clients', lambda: None)
    return exits


def test_in_flight_tracking():
    mgr = ShutdownManager()
    assert mgr.in_flight_count == 0
    assert mgr._drained.is_set()

    mgr.request_started()
    mgr.request_started()
    assert mgr.in_flight_count == 2
    assert not mgr._drained.is_set()

    mgr.request_finished()
    assert mgr.in_flight_count == 1
    assert not mgr._drained.is_set()

    mgr.request_finished()
    assert mgr.in_flight_count == 0
    assert mgr._drained.is_set()


def test_shutdown_waits_for_in_flight(no_exit):
    mgr = ShutdownManager()
    server = FakeServer()
    mgr.register_server(server)
    mgr.request_started()

    def finish_request():
        time.sleep(0.2)
        mgr.request_finished()

    thread = threading.Thread(target=finish_request)
    thread.start()
    mgr.initiate_shutdown(signum=15)
    thread.join()

    assert mgr.is_shutting_down
    assert server.closed
    assert mgr.in_flight_count == 0
    assert no_exit == [0]


def test_shutdown_timeout_forces_exit(no_exit, monkeypatch):
    monkeypatch.setenv('WHOOGLE_SHUTDOWN_TIMEOUT', '0.1')
    mgr = ShutdownManager()
    mgr.request_started()  # never finished

    start = time.time()
    mgr.initiate_shutdown()
    elapsed = time.time() - start

    # Must not block forever on the stuck request
    assert elapsed < 5
    assert mgr.in_flight_count == 1
    assert no_exit == [0]


def test_shutdown_is_idempotent(no_exit):
    mgr = ShutdownManager()
    mgr.initiate_shutdown()
    mgr.initiate_shutdown()
    assert no_exit == [0]


def test_shutdown_timeout_env(monkeypatch):
    mgr = ShutdownManager()
    monkeypatch.setenv('WHOOGLE_SHUTDOWN_TIMEOUT', '7.5')
    assert mgr.shutdown_timeout == 7.5
    monkeypatch.setenv('WHOOGLE_SHUTDOWN_TIMEOUT', 'not-a-number')
    assert mgr.shutdown_timeout == 30.0
