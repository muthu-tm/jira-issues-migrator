import json
import os
import csv
import argparse
from datetime import datetime
from tqdm import tqdm
import requests
from config.settings import settings
from src.utils import make_auth, ensure_dir, load_mapping_config, map_user
from src.logger import logger

class JiraMigrator:
    def __init__(self):
        self._initialize_directories()
        self._initialize_logs()
        self.mapping_config = load_mapping_config()
        self.issue_mapping_file = os.path.join(settings.DATA_DIR, 'mappings', 'issue_mappings.json')
        
        # Initialize issue mappings if file doesn't exist
        if not os.path.exists(self.issue_mapping_file):
            with open(self.issue_mapping_file, 'w') as f:
                json.dump({}, f)

    def _initialize_directories(self):
        ensure_dir(settings.LOG_DIR)
        ensure_dir(os.path.join(settings.DATA_DIR, 'mappings'))
        ensure_dir(os.path.join(settings.LOG_DIR, 'errors'))

    def _initialize_logs(self):
        self.error_files = {
            'issues': os.path.join(settings.LOG_DIR, 'errors', 'issue_migration_errors.csv'),
            'comments': os.path.join(settings.LOG_DIR, 'errors', 'comment_migration_errors.csv'),
            'attachments': os.path.join(settings.LOG_DIR, 'errors', 'attachment_migration_errors.csv')
        }
        
        for log_type, filepath in self.error_files.items():
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    writer = csv.writer(f)
                    if log_type == 'issues':
                        writer.writerow(['source_key', 'error', 'timestamp', 'details'])
                    elif log_type == 'comments':
                        writer.writerow(['source_key', 'target_key', 'comment_id', 'error', 'timestamp'])
                    elif log_type == 'attachments':
                        writer.writerow(['source_key', 'target_key', 'attachment_id', 'filename', 'error', 'timestamp'])

    def migrate_issues(self, limit=None, test_mode=False):
        """Migrate all issues with optional limit and test mode"""
        logger.info(f"Starting issue migration (Test Mode: {test_mode}, Limit: {limit})")
        input_file = os.path.join(settings.EXPORT_DIR, f"{settings.SOURCE_PROJECT_KEY}_issues.json")
        
        with open(input_file) as f:
            issues = json.load(f)['issues']
            if limit:
                issues = issues[:limit]

        success_count = 0
        for issue in tqdm(issues, desc="Migrating issues"):
            try:
                if test_mode:
                    logger.info(f"TEST MODE: Would migrate {issue['key']}")
                    success_count += 1
                    continue
                
                new_key = self._migrate_single_issue(issue)
                if new_key:
                    success_count += 1
                    # Save mapping
                    with open(self.issue_mapping_file, 'r+') as f:
                        mappings = json.load(f)
                        mappings[issue['key']] = new_key
                        f.seek(0)
                        json.dump(mappings, f, indent=2)
                        f.truncate()
                    
                    # Only migrate related data if not in test mode
                    self.migrate_comments(issue['key'], new_key)
                    self.migrate_attachments(issue['key'], new_key)
            except Exception as e:
                logger.error(f"Failed to migrate issue {issue['key']}: {str(e)}")

        logger.info(f"Issue migration complete: {success_count}/{len(issues)} succeeded")
        return success_count

    def _migrate_single_issue(self, issue):
        """Migrate a single issue with field mappings"""
        source_key = issue['key']
        fields = issue['fields']
        
        # Prepare the new issue payload
        new_issue = {
            'fields': {
                'project': {'key': settings.TARGET_PROJECT_KEY},
                'summary': fields.get('summary', 'No summary'),
                'description': fields.get('description', ''),
                'issuetype': self._map_issue_type(fields.get('issuetype')),
                'priority': self._map_priority(fields.get('priority')),
                'labels': fields.get('labels', []) + self.mapping_config['default_values'].get('labels', []),
                'components': self._map_components(fields.get('components', [])),
                'fixVersions': self._map_versions(fields.get('fixVersions', [])),
            }
        }

        # Handle custom fields
        self._map_custom_fields(fields, new_issue)

        # Map users with fallback to default
        self._map_users(fields, new_issue, source_key)

        # Create the issue in target Jira
        try:
            response = requests.post(
                f"{settings.TARGET_JIRA_URL}/rest/api/2/issue",
                json=new_issue,
                auth=make_auth(settings.TARGET_USERNAME, settings.TARGET_PASSWORD),
                timeout=30
            )

            if response.status_code == 201:
                new_issue_key = response.json()['key']
                logger.info(f"Successfully migrated {source_key} to {new_issue_key}")
                return new_issue_key
            else:
                self._log_error('issues', {
                    'source_key': source_key,
                    'error': f"HTTP {response.status_code}",
                    'details': response.text[:500]  # Truncate long responses
                })
                return None

        except Exception as e:
            self._log_error('issues', {
                'source_key': source_key,
                'error': str(e),
                'details': f"Failed during issue creation"
            })
            return None

    def migrate_comments_batch(self, limit=None, test_mode=False):
        """Migrate all comments in batch mode with limit and test mode"""
        logger.info(f"Starting batch comment migration (Test Mode: {test_mode}, Limit: {limit})")
        
        with open(self.issue_mapping_file) as f:
            issue_mappings = json.load(f)
        
        if limit:
            issue_mappings = dict(list(issue_mappings.items())[:limit])

        success_count = 0
        total_comments = 0
        
        for source_key, target_key in tqdm(issue_mappings.items(), desc="Migrating comments"):
            try:
                if test_mode:
                    logger.info(f"TEST MODE: Would migrate comments for {source_key} -> {target_key}")
                    continue
                
                # Get comments from source
                response = requests.get(
                    f"{settings.SOURCE_JIRA_URL}/rest/api/2/issue/{source_key}/comment",
                    auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                    timeout=30
                )

                if response.status_code != 200:
                    self._log_error('comments', {
                        'source_key': source_key,
                        'target_key': target_key,
                        'error': f"Failed to fetch comments: {response.status_code}"
                    })
                    continue

                comments = response.json().get('comments', [])
                total_comments += len(comments)
                
                for comment in comments:
                    try:
                        # Map comment author
                        author_email = comment['author'].get('emailAddress', '')
                        mapped_author = map_user(
                            author_email,
                            self.mapping_config,
                            settings.DEFAULT_USER
                        )

                        # Create comment payload
                        new_comment = {
                            'body': comment['body'],
                            'author': {'emailAddress': mapped_author}
                        }

                        if 'created' in comment:
                            new_comment['created'] = comment['created']

                        # Post to target Jira
                        comment_response = requests.post(
                            f"{settings.TARGET_JIRA_URL}/rest/api/2/issue/{target_key}/comment",
                            json=new_comment,
                            auth=make_auth(settings.TARGET_USERNAME, settings.TARGET_PASSWORD),
                            timeout=30
                        )

                        if comment_response.status_code == 201:
                            success_count += 1
                        else:
                            self._log_error('comments', {
                                'source_key': source_key,
                                'target_key': target_key,
                                'comment_id': comment.get('id'),
                                'error': f"HTTP {comment_response.status_code}"
                            })

                    except Exception as e:
                        self._log_error('comments', {
                            'source_key': source_key,
                            'target_key': target_key,
                            'comment_id': comment.get('id'),
                            'error': str(e)
                        })

            except Exception as e:
                logger.error(f"Error processing comments for {source_key}: {str(e)}")

        logger.info(f"Comment migration complete: {success_count}/{total_comments} succeeded")
        return success_count

    def migrate_attachments_batch(self, limit=None, test_mode=False):
        """Migrate all attachments in batch mode with limit and test mode"""
        logger.info(f"Starting batch attachment migration (Test Mode: {test_mode}, Limit: {limit})")
        
        with open(self.issue_mapping_file) as f:
            issue_mappings = json.load(f)
        
        if limit:
            issue_mappings = dict(list(issue_mappings.items())[:limit])

        success_count = 0
        total_attachments = 0
        
        for source_key, target_key in tqdm(issue_mappings.items(), desc="Migrating attachments"):
            try:
                if test_mode:
                    logger.info(f"TEST MODE: Would migrate attachments for {source_key} -> {target_key}")
                    continue
                
                # Get attachments from source
                issue_response = requests.get(
                    f"{settings.SOURCE_JIRA_URL}/rest/api/2/issue/{source_key}?fields=attachment",
                    auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                    timeout=30
                )

                if issue_response.status_code != 200:
                    self._log_error('attachments', {
                        'source_key': source_key,
                        'target_key': target_key,
                        'error': f"Failed to fetch attachments: {issue_response.status_code}"
                    })
                    continue

                attachments = issue_response.json().get('fields', {}).get('attachment', [])
                total_attachments += len(attachments)
                
                for attachment in attachments:
                    try:
                        # Download attachment
                        file_response = requests.get(
                            attachment['content'],
                            auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                            stream=True,
                            timeout=60
                        )

                        if file_response.status_code != 200:
                            self._log_error('attachments', {
                                'source_key': source_key,
                                'target_key': target_key,
                                'attachment_id': attachment.get('id'),
                                'filename': attachment.get('filename'),
                                'error': f"Download failed: {file_response.status_code}"
                            })
                            continue

                        # Upload to target
                        upload_response = requests.post(
                            f"{settings.TARGET_JIRA_URL}/rest/api/2/issue/{target_key}/attachments",
                            files={'file': (attachment['filename'], file_response.content)},
                            headers={
                                'X-Atlassian-Token': 'no-check',
                                'Accept': 'application/json'
                            },
                            auth=make_auth(settings.TARGET_USERNAME, settings.TARGET_PASSWORD),
                            timeout=60
                        )

                        if upload_response.status_code == 200:
                            success_count += 1
                        else:
                            self._log_error('attachments', {
                                'source_key': source_key,
                                'target_key': target_key,
                                'attachment_id': attachment.get('id'),
                                'filename': attachment.get('filename'),
                                'error': f"Upload failed: {upload_response.status_code}"
                            })

                    except Exception as e:
                        self._log_error('attachments', {
                            'source_key': source_key,
                            'target_key': target_key,
                            'attachment_id': attachment.get('id'),
                            'filename': attachment.get('filename'),
                            'error': str(e)
                        })

            except Exception as e:
                logger.error(f"Error processing attachments for {source_key}: {str(e)}")

        logger.info(f"Attachment migration complete: {success_count}/{total_attachments} succeeded")
        return success_count

    def _log_error(self, error_type, error_data):
        """Log error to appropriate error file"""
        filepath = self.error_files.get(error_type)
        if not filepath:
            logger.error(f"Unknown error type: {error_type}")
            return
            
        with open(filepath, 'a') as f:
            writer = csv.writer(f)
            row = [
                error_data.get('source_key', ''),
                error_data.get('target_key', ''),
                error_data.get('comment_id', ''),
                error_data.get('attachment_id', ''),
                error_data.get('filename', ''),
                error_data.get('error', 'Unknown error'),
                datetime.now().isoformat(),
                str(error_data.get('details', ''))[:500]  # Truncate long details
            ]
            writer.writerow(row)

    # Helper methods for field mappings
    def _map_issue_type(self, source_type):
        if not source_type:
            return {'name': 'Task'}
        target_name = self.mapping_config['issue_types'].get(source_type['name'], source_type['name'])
        return {'name': target_name}

    def _map_priority(self, source_priority):
        if not source_priority:
            return {'name': 'Medium'}
        target_name = self.mapping_config['priorities'].get(source_priority['name'], source_priority['name'])
        return {'name': target_name}

    def _map_components(self, source_components):
        mapped = []
        for comp in source_components:
            target_name = self.mapping_config['components'].get(comp['name'], comp['name'])
            mapped.append({'name': target_name})
        return mapped or [{'name': name} for name in self.mapping_config['default_values'].get('components', [])]

    def _map_versions(self, source_versions):
        mapped = []
        for version in source_versions:
            target_name = self.mapping_config['versions'].get(version['name'], version['name'])
            mapped.append({'name': target_name})
        return mapped or [{'name': name} for name in self.mapping_config['default_values'].get('fixVersions', [])]

    def _map_custom_fields(self, source_fields, target_issue):
        for source_id, target_id in self.mapping_config['custom_fields'].items():
            if source_id in source_fields:
                target_issue['fields'][target_id] = source_fields[source_id]

    def _map_users(self, source_fields, target_issue, source_key):
        user_fields = ['reporter', 'assignee']
        for field in user_fields:
            if field in source_fields and source_fields[field]:
                email = source_fields[field].get('emailAddress', '')
                mapped_email = map_user(email, self.mapping_config, settings.DEFAULT_USER)
                
                if mapped_email == settings.DEFAULT_USER and email:
                    self._log_unmapped_user(source_key, email, field)
                
                target_issue['fields'][field] = {'emailAddress': mapped_email}

    def _log_unmapped_user(self, issue_key, original_email, field_name):
        with open(self.unmapped_users_log, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([issue_key, original_email, settings.DEFAULT_USER, field_name])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--issues', action='store_true', help='Migrate only issues')
    parser.add_argument('--comments', action='store_true', help='Migrate only comments')
    parser.add_argument('--attachments', action='store_true', help='Migrate only attachments')
    parser.add_argument('--all', action='store_true', help='Migrate everything')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no actual migration)')
    parser.add_argument('--limit', type=int, help='Limit number of items to process')
    args = parser.parse_args()

    migrator = JiraMigrator()
    if args.issues:
        migrator.migrate_issues(limit=args.limit, test_mode=args.test)
    elif args.comments:
        migrator.migrate_comments_batch(limit=args.limit, test_mode=args.test)
    elif args.attachments:
        migrator.migrate_attachments_batch(limit=args.limit, test_mode=args.test)
    elif args.all:
        migrator.migrate_issues(limit=args.limit, test_mode=args.test)
        if not args.test:  # Only migrate related data if not in test mode
            migrator.migrate_comments_batch(limit=args.limit, test_mode=args.test)
            migrator.migrate_attachments_batch(limit=args.limit, test_mode=args.test)