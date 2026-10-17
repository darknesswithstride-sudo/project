from pathlib import Path
import json
import pytest
from app import studio_pipeline

def test_input_rejects_path_outside_workspace():
    with pytest.raises(ValueError): studio_pipeline._input("../../etc/passwd")

def test_job_id_validation():
    with pytest.raises(ValueError): studio_pipeline.get_job("../../etc/passwd")

def test_job_list_is_list():
    assert isinstance(studio_pipeline.list_jobs(), list)
