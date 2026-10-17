from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_home_has_local_free_release():
    response = client.get('/')
    assert response.status_code == 200
    assert 'Autonomous local intelligence' in response.text
    assert 'What should I build for you?' in response.text
    assert 'sideNav' not in response.text


def test_status_marks_free_local_only():
    response = client.get('/api/status')
    assert response.status_code == 200
    data = response.json()
    assert data['free_local_only'] is True
    assert data['remote_paid_providers_enabled'] is False
    assert data['3d_provider'] == 'local'


def test_diagnostics_endpoint():
    response = client.get('/api/diagnostics')
    assert response.status_code == 200
    data = response.json()
    assert data['paid_api_calls'] is False
    assert 'ollama' in data['checks']
    assert 'blender' in data['checks']
    assert 'triposr' in data['checks']


def test_api_docs_available():
    response = client.get('/api/docs')
    assert response.status_code == 200


def test_chat_only_interface_and_local_only_ui():
    response = client.get('/')
    assert response.status_code == 200
    assert 'Autonomous local intelligence' in response.text
    assert 'Persistent project memory' in response.text
    assert 'sectionSearch' not in response.text
    assert 'fonts.googleapis.com' not in response.text


def test_release_version_is_46():
    response = client.get('/api/status')
    assert response.status_code == 200
    assert response.json()['version'] == '4.7.0'


def test_studio_catalog_endpoint():
    response = client.get('/api/studio/catalog')
    assert response.status_code == 200
    data = response.json()
    assert data['studio_version'] == '4.7.0'
    assert data['local_only'] is True
    assert 'assets' in data and 'backends' in data and 'workflow' in data

def test_chat_interface_replaces_studio_dashboard():
    response = client.get('/')
    assert response.status_code == 200
    assert 'What should I build for you?' in response.text
    assert 'sendMessage()' in response.text
    assert 'image' in response.text
    assert 'Forge Studio' not in response.text


def test_chat_ui_and_autonomy_endpoints_exist():
    response = client.get('/')
    assert response.status_code == 200
    assert 'runAutonomy()' not in response.text
    assert 'sendMessage()' in response.text
    assert client.get('/api/chat/jobs').status_code == 200
    assert client.get('/api/autonomy/jobs').status_code == 200


def test_autonomy_command_endpoint_dispatches_to_engine(monkeypatch):
    from app import autonomous_engine
    async def fake_run(command, project_path='.', max_actions=4):
        return {'job_id':'abc12345','status':'SUCCEEDED','command':command,'project_path':project_path,'max_actions':max_actions}
    monkeypatch.setattr(autonomous_engine, 'run_autonomous_task', fake_run)
    response = client.post('/api/autonomy/run', data={'command':'Run the tests', 'project_path':'.', 'max_actions':'2'})
    assert response.status_code == 200
    assert response.json()['command'] == 'Run the tests'
    assert response.json()['max_actions'] == 2


def test_chat_history_and_sessions_endpoints():
    assert client.get('/api/chat/history/default').status_code == 200
    assert client.get('/api/chat/sessions').status_code == 200
    assert client.get('/api/chat/jobs').status_code == 200

def test_capability_registry_and_unreal_diagnostics_endpoints():
    assert client.get('/api/capabilities').status_code == 200
    assert client.get('/api/unreal/installation').status_code == 200
    result = client.post('/api/capabilities/register-verified', json={
        'manifest': {'id':'endpoint_smoke_test','name':'Endpoint smoke test','description':'Testing registration'},
        'source': 'assert 6 * 7 == 42\nprint("ok")\n'
    })
    assert result.status_code == 200
    assert result.json()['registered'] is True

def test_capability_endpoint_rejects_unsafe_smoke_test():
    result = client.post('/api/capabilities/register-verified', json={
        'manifest': {'id':'unsafe_endpoint_test','name':'Unsafe','description':'Must be rejected'},
        'source': 'import os\nprint(os.getcwd())\n'
    })
    assert result.status_code == 200
    assert result.json()['registered'] is False
    assert result.json()['status'] == 'REJECTED'
