import pytest
import os
import json
from src.migrator import JiraMigrator
from config.settings import settings

@pytest.fixture
def test_migrator(tmp_path):
    # Setup test directories
    settings.DATA_DIR = str(tmp_path)
    settings.EXPORT_DIR = os.path.join(settings.DATA_DIR, 'exported')
    settings.LOG_DIR = os.path.join(settings.DATA_DIR, 'logs')
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    
    # Create test issue file
    test_issues = {
        "issues": [
            {
                "key": "TEST-1",
                "fields": {
                    "summary": "Test Issue",
                    "description": "Test Description",
                    "reporter": {"emailAddress": "user1@example.com"},
                    "attachment": []
                }
            }
        ]
    }
    
    with open(os.path.join(settings.EXPORT_DIR, f"{settings.SOURCE_PROJECT_KEY}_issues.json"), 'w') as f:
        json.dump(test_issues, f)
    
    return JiraMigrator()

@pytest.fixture
def test_mapping_file(tmp_path):
    mapping_file = os.path.join(tmp_path, 'issue_mappings.json')
    with open(mapping_file, 'w') as f:
        json.dump({"TEST-1": "NEW-1"}, f)
    return mapping_file