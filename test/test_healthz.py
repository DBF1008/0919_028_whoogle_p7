import json

from app import app
from app import routes


def _get_healthz(client):
    rv = client.get('/healthz')
    return rv, json.loads(rv.data)


def test_healthz_ok(client, monkeypatch):
    monkeypatch.setattr(routes, '_check_google_connectivity', lambda: True)
    monkeypatch.setattr(routes, '_check_config_dir', lambda: True)
    rv, data = _get_healthz(client)
    assert rv.status_code == 200
    assert data['status'] == 'ok'
    assert data['checks']['google_connectivity'] is True
    assert data['checks']['config_dir'] is True


def test_healthz_google_unreachable(client, monkeypatch):
    monkeypatch.setattr(routes, '_check_google_connectivity', lambda: False)
    monkeypatch.setattr(routes, '_check_config_dir', lambda: True)
    rv, data = _get_healthz(client)
    assert rv.status_code == 503
    assert data['status'] == 'error'
    assert data['checks']['google_connectivity'] is False
    assert data['checks']['config_dir'] is True


def test_healthz_config_dir_inaccessible(client, monkeypatch):
    monkeypatch.setattr(routes, '_check_google_connectivity', lambda: True)
    monkeypatch.setattr(routes, '_check_config_dir', lambda: False)
    rv, data = _get_healthz(client)
    assert rv.status_code == 503
    assert data['status'] == 'error'
    assert data['checks']['config_dir'] is False


def test_check_config_dir_missing(monkeypatch):
    monkeypatch.setitem(app.config, 'CONFIG_PATH',
                        '/nonexistent/whoogle/config')
    assert routes._check_config_dir() is False


def test_check_config_dir_ok(tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, 'CONFIG_PATH', str(tmp_path))
    assert routes._check_config_dir() is True


def test_check_google_connectivity_success(monkeypatch):
    class FakeResponse:
        status_code = 204

    monkeypatch.setattr(routes.httpx, 'head',
                        lambda *args, **kwargs: FakeResponse())
    assert routes._check_google_connectivity() is True


def test_check_google_connectivity_failure(monkeypatch):
    def raise_connect_error(*args, **kwargs):
        raise routes.httpx.ConnectError('connection refused')

    monkeypatch.setattr(routes.httpx, 'head', raise_connect_error)
    assert routes._check_google_connectivity() is False
