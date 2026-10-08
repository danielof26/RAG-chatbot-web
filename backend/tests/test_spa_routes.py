import os

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    dist = tmp_path / 'dist'
    (dist / 'assets').mkdir(parents=True)
    (dist / 'index.html').write_text('<html>SPA</html>')
    (dist / 'assets' / 'app.js').write_text('console.log(1)')
    monkeypatch.setattr(app_module, 'FRONTEND_DIST', str(dist))
    return app_module.app.test_client()


def test_root_and_spa_subroutes_serve_index(client):
    assert b'SPA' in client.get('/').data
    for path in ('/agents', '/agents/65f0c0ffee0000000000abcd', '/llm-servers'):
        res = client.get(path)
        assert res.status_code == 200 and b'SPA' in res.data, path


def test_static_assets_are_served(client):
    res = client.get('/assets/app.js')
    assert res.status_code == 200 and b'console.log' in res.data


def test_api_routes_are_not_shadowed(client):
    assert client.get('/api/rag/techniques').status_code == 401  # reaches the view (token required)
