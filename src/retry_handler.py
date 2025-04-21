import argparse
import csv
import json
import os
from tqdm import tqdm
from datetime import datetime
from config.settings import settings
from src.utils import make_auth, map_user
from src.logger import logger
from src.migrator import JiraMigrator
import requests

class RetryHandler:
    def __init__(self):
        self.migrator = JiraMigrator()
        self.error_files = self.migrator.log_files

    def retry_failed_issues(self, max_retries=3):
        """Retry failed issue migrations"""
        logger.info("Retrying failed issue migrations")
    
        # Load original exported issues
        with open(os.path.join(settings.EXPORT_DIR, f"{settings.SOURCE_PROJECT_KEY}_issues.json")) as f:
            exported_issues = {issue['key']: issue for issue in json.load(f)['issues']}
        
        # Read error file and group by issue key
        with open(self.error_files['issues']) as f:
            reader = csv.DictReader(f)
            failed_issues = {row['source_key']: row for row in reader}
        
        if not failed_issues:
            logger.info("No failed issues to retry")
            return
        
        retry_count = 0
        success_count = 0
        
        for source_key, error_info in tqdm(failed_issues.items(), desc="Retrying failed issues"):
            if retry_count >= max_retries:
                logger.warning(f"Max retries ({max_retries}) reached for issues")
                break
                
            if source_key not in exported_issues:
                logger.warning(f"Original issue not found for {source_key}")
                continue
                
            issue = exported_issues[source_key]
            new_key = self.migrate_issue(issue)
            
            if new_key:
                success_count += 1
                # Update mapping file if successful
                with open(self.issue_mapping_file, 'r+') as f:
                    mappings = json.load(f)
                    mappings[source_key] = new_key
                    f.seek(0)
                    json.dump(mappings, f, indent=2)
                    f.truncate()
            
            retry_count += 1
        
        logger.info(f"Retried {retry_count} failed issues, {success_count} succeeded")
        pass

    def retry_failed_comments(self, max_retries=3):
        """Retry failed comment migrations"""
        logger.info("Retrying failed comment migrations")
    
        # Load issue mappings
        with open(self.issue_mapping_file) as f:
            issue_mappings = json.load(f)
        
        # Read error file and group by issue key
        with open(self.error_files['comments']) as f:
            reader = csv.DictReader(f)
            failed_comments = {}
            for row in reader:
                if row['source_key'] not in failed_comments:
                    failed_comments[row['source_key']] = []
                failed_comments[row['source_key']].append(row)
        
        if not failed_comments:
            logger.info("No failed comments to retry")
            return
        
        retry_count = 0
        success_count = 0
        
        for source_key, errors in tqdm(failed_comments.items(), desc="Retrying failed comments"):
            if retry_count >= max_retries:
                logger.warning(f"Max retries ({max_retries}) reached for comments")
                break
                
            if source_key not in issue_mappings:
                logger.warning(f"No target issue found for {source_key}")
                continue
                
            target_key = issue_mappings[source_key]
            
            # Get all comments for the issue
            try:
                response = requests.get(
                    f"{settings.SOURCE_JIRA_URL}/rest/api/2/issue/{source_key}/comment",
                    auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch comments for {source_key}")
                    continue
                    
                all_comments = response.json().get('comments', [])
                
                # Filter to only failed comments
                failed_comment_ids = {e['comment_id'] for e in errors}
                comments_to_retry = [c for c in all_comments if str(c['id']) in failed_comment_ids]
                
                for comment in comments_to_retry:
                    try:
                        # Same migration logic as original
                        author_email = comment['author'].get('emailAddress', '')
                        mapped_author = map_user(
                            author_email,
                            self.mapping_config,
                            settings.DEFAULT_USER
                        )
                        
                        new_comment = {
                            'body': comment['body'],
                            'author': {'emailAddress': mapped_author}
                        }
                        
                        if 'created' in comment:
                            new_comment['created'] = comment['created']
                        
                        response = requests.post(
                            f"{settings.TARGET_JIRA_URL}/rest/api/2/issue/{target_key}/comment",
                            json=new_comment,
                            auth=make_auth(settings.TARGET_USERNAME, settings.TARGET_PASSWORD),
                            timeout=30
                        )
                        
                        if response.status_code == 201:
                            success_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to retry comment {comment['id']}: {str(e)}")
                    
                    retry_count += 1
                    
            except Exception as e:
                logger.error(f"Error retrying comments for {source_key}: {str(e)}")
        
        logger.info(f"Retried {retry_count} failed comments, {success_count} succeeded")
        pass

    def retry_failed_attachments(self, max_retries=3):
        """Retry failed attachment migrations"""
        logger.info("Retrying failed attachment migrations")
        
        # Load issue mappings
        with open(self.issue_mapping_file) as f:
            issue_mappings = json.load(f)
        
        # Read error file and group by issue key
        with open(self.error_files['attachments']) as f:
            reader = csv.DictReader(f)
            failed_attachments = {}
            for row in reader:
                if row['source_key'] not in failed_attachments:
                    failed_attachments[row['source_key']] = []
                failed_attachments[row['source_key']].append(row)
        
        if not failed_attachments:
            logger.info("No failed attachments to retry")
            return
        
        retry_count = 0
        success_count = 0
        
        for source_key, errors in tqdm(failed_attachments.items(), desc="Retrying failed attachments"):
            if retry_count >= max_retries:
                logger.warning(f"Max retries ({max_retries}) reached for attachments")
                break
                
            if source_key not in issue_mappings:
                logger.warning(f"No target issue found for {source_key}")
                continue
                
            target_key = issue_mappings[source_key]
            
            # Get all attachments for the issue
            try:
                response = requests.get(
                    f"{settings.SOURCE_JIRA_URL}/rest/api/2/issue/{source_key}?fields=attachment",
                    auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch attachments for {source_key}")
                    continue
                    
                all_attachments = response.json().get('fields', {}).get('attachment', [])
                
                # Filter to only failed attachments
                failed_attachment_ids = {e['attachment_id'] for e in errors}
                attachments_to_retry = [a for a in all_attachments if str(a['id']) in failed_attachment_ids]
                
                for attachment in attachments_to_retry:
                    try:
                        # Download attachment
                        file_response = requests.get(
                            attachment['content'],
                            auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                            stream=True,
                            timeout=60
                        )
                        
                        if file_response.status_code != 200:
                            continue
                        
                        # Upload to target
                        upload_response = requests.post(
                            f"{settings.TARGET_JIRA_URL}/rest/api/2/issue/{target_key}/attachments",
                            files={'file': (attachment['filename'], file_response.content)},
                            headers={'X-Atlassian-Token': 'no-check'},
                            auth=make_auth(settings.TARGET_USERNAME, settings.TARGET_PASSWORD),
                            timeout=60
                        )
                        
                        if upload_response.status_code == 200:
                            success_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to retry attachment {attachment['id']}: {str(e)}")
                    
                    retry_count += 1
                    
            except Exception as e:
                logger.error(f"Error retrying attachments for {source_key}: {str(e)}")
        
        logger.info(f"Retried {retry_count} failed attachments, {success_count} succeeded")
        pass

    def full_retry(self, max_retries=3):
        """Retry all failed migrations"""
        logger.info("Starting full retry of failed migrations")
        self.retry_failed_issues(max_retries)
        self.retry_failed_comments(max_retries)
        self.retry_failed_attachments(max_retries)
        logger.info("Full retry completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--issues', action='store_true', help='Retry failed issues')
    parser.add_argument('--comments', action='store_true', help='Retry failed comments')
    parser.add_argument('--attachments', action='store_true', help='Retry failed attachments')
    parser.add_argument('--all', action='store_true', help='Retry all failed migrations')
    parser.add_argument('--retries', type=int, default=3, help='Max retry attempts')
    args = parser.parse_args()

    handler = RetryHandler()
    if args.issues:
        handler.retry_failed_issues(args.retries)
    elif args.comments:
        handler.retry_failed_comments(args.retries)
    elif args.attachments:
        handler.retry_failed_attachments(args.retries)
    elif args.all:
        handler.full_retry(args.retries)