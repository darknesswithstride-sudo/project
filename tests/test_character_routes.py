from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_character_jobs_endpoint():
    response = client.get('/api/studio/character-jobs')
    assert response.status_code == 200
    assert isinstance(response.json()['jobs'], list)

def test_character_job_invalid_id_rejected():
    response = client.get('/api/studio/character-jobs/../../etc/passwd')
    assert response.status_code in (404, 422)

def test_character_pipeline_requires_reference_file():
    response = client.post('/api/studio/character-pipeline', data={'prompt':'test'})
    assert response.status_code == 422
