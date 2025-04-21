import pytest
from unittest.mock import patch, MagicMock

def test_migrate_issues(test_migrator):
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"key": "NEW-1"}
        mock_post.return_value = mock_response
        
        migrated_count, failed_issues = test_migrator.migrate(limit=1)
        
        assert migrated_count == 1
        assert len(failed_issues) == 0

def test_migrate_comments_only(test_migrator, test_mapping_file):
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        # Mock comments response
        mock_comments_response = MagicMock()
        mock_comments_response.status_code = 200
        mock_comments_response.json.return_value = {"comments": [{"body": "Test comment", "author": {"emailAddress": "user1@example.com"}}]}
        mock_get.return_value = mock_comments_response
        
        # Mock successful post
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response
        
        migrated_count, failed_issues = test_migrator.migrate(comments_only=True, mapping_file=test_mapping_file)
        
        assert migrated_count == 1
        assert len(failed_issues) == 0

def test_migrate_attachments_only(test_migrator, test_mapping_file):
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        # Mock attachments response
        mock_attachments_response = MagicMock()
        mock_attachments_response.status_code = 200
        mock_attachments_response.json.return_value = {
            "fields": {
                "attachment": [
                    {"filename": "test.txt", "content": "http://example.com/attachment"}
                ]
            }
        }
        mock_get.return_value = mock_attachments_response
        
        # Mock successful post
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post.return_value = mock_post_response
        
        migrated_count, failed_issues = test_migrator.migrate(attachments_only=True, mapping_file=test_mapping_file)
        
        assert migrated_count == 1
        assert len(failed_issues) == 0