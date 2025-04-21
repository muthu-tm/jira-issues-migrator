import json
import os
import csv
from datetime import datetime
from collections import defaultdict
import requests
from tqdm import tqdm
from config.settings import settings
from src.utils import make_auth, ensure_dir
from src.logger import logger

class MigrationValidator:
    def __init__(self):
        ensure_dir(settings.LOG_DIR)
        self.validation_file = os.path.join(settings.LOG_DIR, 'validation_results.json')
        self.error_file = os.path.join(settings.LOG_DIR, 'validation_errors.csv')
        
        # Initialize error log
        if not os.path.exists(self.error_file):
            with open(self.error_file, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(['validation_type', 'source_key', 'target_key', 'error', 'timestamp'])

    def full_validation(self):
        """Run complete validation of all migration aspects"""
        logger.info("Starting full migration validation")
        
        results = {
            'summary': defaultdict(dict),
            'details': defaultdict(list),
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # 1. Validate basic counts
            results.update(self.validate_counts())
            
            # 2. Validate issue mappings
            results.update(self.validate_issue_mappings())
            
            # 3. Validate sample content
            results.update(self.validate_sample_content())
            
            # 4. Validate attachments
            results.update(self.validate_attachments())
            
            # 5. Validate comments
            results.update(self.validate_comments())
            
            # Save results
            with open(self.validation_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"Validation complete. Results saved to {self.validation_file}")
            return results
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            raise

    def validate_counts(self):
        """Validate basic counts of issues, comments, and attachments"""
        logger.info("Validating basic counts")
        
        results = {
            'summary': {},
            'details': {}
        }
        
        # Get source counts
        source_counts = self._get_project_counts(
            settings.SOURCE_JIRA_URL,
            settings.SOURCE_USERNAME,
            settings.SOURCE_PASSWORD,
            settings.SOURCE_PROJECT_KEY
        )
        
        # Get target counts
        target_counts = self._get_project_counts(
            settings.TARGET_JIRA_URL,
            settings.TARGET_USERNAME,
            settings.TARGET_PASSWORD,
            settings.TARGET_PROJECT_KEY
        )
        
        # Compare counts
        for metric in ['issues', 'comments', 'attachments']:
            results['summary'][f'{metric}_count'] = {
                'source': source_counts.get(metric, 0),
                'target': target_counts.get(metric, 0),
                'match': source_counts.get(metric, 0) == target_counts.get(metric, 0)
            }
            
            if not results['summary'][f'{metric}_count']['match']:
                self._log_validation_error(
                    'count_validation',
                    '',
                    '',
                    f"Count mismatch for {metric}: source={source_counts.get(metric, 0)} vs target={target_counts.get(metric, 0)}"
                )
        
        return results

    def validate_issue_mappings(self):
        """Validate that all source issues exist in target with correct mappings"""
        logger.info("Validating issue mappings")
        
        results = {
            'summary': {
                'mapped_issues': {'total': 0, 'valid': 0}
            },
            'details': {
                'invalid_mappings': []
            }
        }
        
        # Load exported issues
        with open(os.path.join(settings.EXPORT_DIR, f"{settings.SOURCE_PROJECT_KEY}_issues.json")) as f:
            source_issues = json.load(f)['issues']
        
        # Load issue mappings
        with open(os.path.join(settings.DATA_DIR, 'mappings', 'issue_mappings.json')) as f:
            issue_mappings = json.load(f)
        
        results['summary']['mapped_issues']['total'] = len(issue_mappings)
        
        for source_issue in tqdm(source_issues, desc="Validating issues"):
            source_key = source_issue['key']
            if source_key not in issue_mappings:
                self._log_validation_error(
                    'issue_mapping',
                    source_key,
                    '',
                    "Source issue not mapped"
                )
                results['details']['invalid_mappings'].append({
                    'source_key': source_key,
                    'error': 'Not mapped'
                })
                continue
                
            target_key = issue_mappings[source_key]
            if not self._issue_exists(settings.TARGET_JIRA_URL, target_key):
                self._log_validation_error(
                    'issue_mapping',
                    source_key,
                    target_key,
                    "Target issue not found"
                )
                results['details']['invalid_mappings'].append({
                    'source_key': source_key,
                    'target_key': target_key,
                    'error': 'Target issue not found'
                })
                continue
                
            # Validate field mappings
            field_errors = self._validate_issue_fields(source_issue, target_key)
            if field_errors:
                for error in field_errors:
                    self._log_validation_error(
                        'field_mapping',
                        source_key,
                        target_key,
                        error
                    )
                results['details']['invalid_mappings'].append({
                    'source_key': source_key,
                    'target_key': target_key,
                    'errors': field_errors
                })
                continue
                
            results['summary']['mapped_issues']['valid'] += 1
        
        return results

    def validate_sample_content(self, sample_size=5):
        """Validate content of a sample of issues"""
        logger.info(f"Validating sample content ({sample_size} issues)")
        
        results = {
            'summary': {
                'content_validation': {'total': 0, 'valid': 0}
            },
            'details': {
                'content_errors': []
            }
        }
        
        # Load issue mappings
        with open(os.path.join(settings.DATA_DIR, 'mappings', 'issue_mappings.json')) as f:
            issue_mappings = json.load(f)
        
        # Get a sample of issues
        sample_keys = list(issue_mappings.keys())[:sample_size]
        
        for source_key in tqdm(sample_keys, desc="Validating content"):
            target_key = issue_mappings[source_key]
            
            # Get source issue
            source_issue = self._get_issue(
                settings.SOURCE_JIRA_URL,
                settings.SOURCE_USERNAME,
                settings.SOURCE_PASSWORD,
                source_key
            )
            
            # Get target issue
            target_issue = self._get_issue(
                settings.TARGET_JIRA_URL,
                settings.TARGET_USERNAME,
                settings.TARGET_PASSWORD,
                target_key
            )
            
            if not source_issue or not target_issue:
                continue
                
            results['summary']['content_validation']['total'] += 1
            
            # Compare key fields
            comparison = self._compare_issues(source_issue, target_issue)
            if comparison['match']:
                results['summary']['content_validation']['valid'] += 1
            else:
                results['details']['content_errors'].append({
                    'source_key': source_key,
                    'target_key': target_key,
                    'errors': comparison['differences']
                })
                for error in comparison['differences']:
                    self._log_validation_error(
                        'content_validation',
                        source_key,
                        target_key,
                        error
                    )
        
        return results

    def validate_comments(self, sample_size=5):
        """Validate comments for a sample of issues"""
        logger.info(f"Validating comments ({sample_size} issues)")
        
        results = {
            'summary': {
                'comment_validation': {'total': 0, 'valid': 0}
            },
            'details': {
                'comment_errors': []
            }
        }
        
        # Load issue mappings
        with open(os.path.join(settings.DATA_DIR, 'mappings', 'issue_mappings.json')) as f:
            issue_mappings = json.load(f)
        
        # Get a sample of issues
        sample_keys = list(issue_mappings.keys())[:sample_size]
        
        for source_key in tqdm(sample_keys, desc="Validating comments"):
            target_key = issue_mappings[source_key]
            
            # Get source comments
            source_comments = self._get_comments(
                settings.SOURCE_JIRA_URL,
                settings.SOURCE_USERNAME,
                settings.SOURCE_PASSWORD,
                source_key
            )
            
            # Get target comments
            target_comments = self._get_comments(
                settings.TARGET_JIRA_URL,
                settings.TARGET_USERNAME,
                settings.TARGET_PASSWORD,
                target_key
            )
            
            if source_comments is None or target_comments is None:
                continue
                
            results['summary']['comment_validation']['total'] += 1
            
            # Compare comments
            comparison = self._compare_comments(source_comments, target_comments)
            if comparison['match']:
                results['summary']['comment_validation']['valid'] += 1
            else:
                results['details']['comment_errors'].append({
                    'source_key': source_key,
                    'target_key': target_key,
                    'errors': comparison['differences']
                })
                for error in comparison['differences']:
                    self._log_validation_error(
                        'comment_validation',
                        source_key,
                        target_key,
                        error
                    )
        
        return results

    def validate_attachments(self, sample_size=5):
        """Validate attachments for a sample of issues"""
        logger.info(f"Validating attachments ({sample_size} issues)")
        
        results = {
            'summary': {
                'attachment_validation': {'total': 0, 'valid': 0}
            },
            'details': {
                'attachment_errors': []
            }
        }
        
        # Load issue mappings
        with open(os.path.join(settings.DATA_DIR, 'mappings', 'issue_mappings.json')) as f:
            issue_mappings = json.load(f)
        
        # Get a sample of issues
        sample_keys = list(issue_mappings.keys())[:sample_size]
        
        for source_key in tqdm(sample_keys, desc="Validating attachments"):
            target_key = issue_mappings[source_key]
            
            # Get source attachments
            source_attachments = self._get_attachments(
                settings.SOURCE_JIRA_URL,
                settings.SOURCE_USERNAME,
                settings.SOURCE_PASSWORD,
                source_key
            )
            
            # Get target attachments
            target_attachments = self._get_attachments(
                settings.TARGET_JIRA_URL,
                settings.TARGET_USERNAME,
                settings.TARGET_PASSWORD,
                target_key
            )
            
            if source_attachments is None or target_attachments is None:
                continue
                
            results['summary']['attachment_validation']['total'] += 1
            
            # Compare attachments
            comparison = self._compare_attachments(source_attachments, target_attachments)
            if comparison['match']:
                results['summary']['attachment_validation']['valid'] += 1
            else:
                results['details']['attachment_errors'].append({
                    'source_key': source_key,
                    'target_key': target_key,
                    'errors': comparison['differences']
                })
                for error in comparison['differences']:
                    self._log_validation_error(
                        'attachment_validation',
                        source_key,
                        target_key,
                        error
                    )
        
        return results

    # Helper methods
    def _get_project_counts(self, jira_url, username, password, project_key):
        """Get counts of issues, comments and attachments for a project"""
        counts = {
            'issues': 0,
            'comments': 0,
            'attachments': 0
        }
        
        # Get issue count
        counts['issues'] = self._get_jql_count(
            jira_url, username, password,
            f"project={project_key}"
        )
        
        # Get comment count
        counts['comments'] = self._get_jql_count(
            jira_url, username, password,
            f"project={project_key} AND comment IS NOT EMPTY"
        )
        
        # Get attachment count
        counts['attachments'] = self._get_jql_count(
            jira_url, username, password,
            f"project={project_key} AND attachments IS NOT EMPTY"
        )
        
        return counts

    def _get_jql_count(self, jira_url, username, password, jql):
        """Get count of issues matching JQL"""
        url = f"{jira_url}/rest/api/2/search?jql={jql}&maxResults=0"
        try:
            response = requests.get(
                url,
                auth=make_auth(username, password),
                timeout=30
            )
            return response.json().get('total', 0) if response.status_code == 200 else 0
        except Exception as e:
            logger.error(f"Error getting count for JQL {jql}: {str(e)}")
            return 0

    def _issue_exists(self, jira_url, issue_key):
        """Check if an issue exists"""
        url = f"{jira_url}/rest/api/2/issue/{issue_key}"
        try:
            response = requests.get(
                url,
                auth=make_auth(settings.TARGET_USERNAME, settings.TARGET_PASSWORD),
                timeout=30
            )
            return response.status_code == 200
        except Exception:
            return False

    def _get_issue(self, jira_url, username, password, issue_key):
        """Get full issue details"""
        url = f"{jira_url}/rest/api/2/issue/{issue_key}"
        try:
            response = requests.get(
                url,
                auth=make_auth(username, password),
                timeout=30
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error getting issue {issue_key}: {str(e)}")
            return None

    def _get_comments(self, jira_url, username, password, issue_key):
        """Get all comments for an issue"""
        url = f"{jira_url}/rest/api/2/issue/{issue_key}/comment"
        try:
            response = requests.get(
                url,
                auth=make_auth(username, password),
                timeout=30
            )
            return response.json().get('comments', []) if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error getting comments for {issue_key}: {str(e)}")
            return None

    def _get_attachments(self, jira_url, username, password, issue_key):
        """Get all attachments for an issue"""
        url = f"{jira_url}/rest/api/2/issue/{issue_key}?fields=attachment"
        try:
            response = requests.get(
                url,
                auth=make_auth(username, password),
                timeout=30
            )
            return response.json().get('fields', {}).get('attachment', []) if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error getting attachments for {issue_key}: {str(e)}")
            return None

    def _compare_issues(self, source_issue, target_issue):
        """Compare key fields between source and target issues"""
        differences = []
        fields_to_compare = ['summary', 'description', 'issuetype', 'priority', 'status']
        
        for field in fields_to_compare:
            source_value = str(source_issue['fields'].get(field, ''))
            target_value = str(target_issue['fields'].get(field, ''))
            
            if source_value != target_value:
                differences.append(f"Field {field} mismatch: source='{source_value}' vs target='{target_value}'")
        
        return {
            'match': len(differences) == 0,
            'differences': differences
        }

    def _compare_comments(self, source_comments, target_comments):
        """Compare comments between source and target issues"""
        differences = []
        
        # Check count
        if len(source_comments) != len(target_comments):
            differences.append(f"Comment count mismatch: source={len(source_comments)} vs target={len(target_comments)}")
        
        # Compare content of matching comments
        min_comments = min(len(source_comments), len(target_comments))
        for i in range(min_comments):
            if source_comments[i]['body'] != target_comments[i]['body']:
                differences.append(f"Comment body mismatch at position {i}")
        
        return {
            'match': len(differences) == 0,
            'differences': differences
        }

    def _compare_attachments(self, source_attachments, target_attachments):
        """Compare attachments between source and target issues"""
        differences = []
        
        # Check count
        if len(source_attachments) != len(target_attachments):
            differences.append(f"Attachment count mismatch: source={len(source_attachments)} vs target={len(target_attachments)}")
        
        # Compare filenames
        source_files = {a['filename'] for a in source_attachments}
        target_files = {a['filename'] for a in target_attachments}
        
        if source_files != target_files:
            missing = source_files - target_files
            extra = target_files - source_files
            if missing:
                differences.append(f"Missing attachments: {', '.join(missing)}")
            if extra:
                differences.append(f"Extra attachments: {', '.join(extra)}")
        
        return {
            'match': len(differences) == 0,
            'differences': differences
        }

    def _validate_issue_fields(self, source_issue, target_key):
        """Validate field mappings for a specific issue"""
        errors = []
        
        # Get target issue
        target_issue = self._get_issue(
            settings.TARGET_JIRA_URL,
            settings.TARGET_USERNAME,
            settings.TARGET_PASSWORD,
            target_key
        )
        
        if not target_issue:
            return ["Target issue not found"]
        
        # Compare key fields
        comparison = self._compare_issues(source_issue, target_issue)
        errors.extend(comparison['differences'])
        
        return errors

    def _log_validation_error(self, validation_type, source_key, target_key, error):
        """Log validation error to CSV file"""
        with open(self.error_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([
                validation_type,
                source_key,
                target_key,
                error,
                datetime.now().isoformat()
            ])
        logger.warning(f"Validation error ({validation_type}): {source_key}->{target_key} - {error}")

if __name__ == "__main__":
    validator = MigrationValidator()
    results = validator.full_validation()
    
    # Print summary
    print("\n=== Validation Summary ===")
    for category, data in results['summary'].items():
        if isinstance(data, dict) and 'total' in data:
            print(f"{category.replace('_', ' ').title()}: {data['valid']}/{data['total']} valid")
        else:
            print(f"{category.replace('_', ' ').title()}: {json.dumps(data, indent=2)}")
    
    # Save detailed report
    report_file = os.path.join(settings.LOG_DIR, 'validation_report.txt')
    with open(report_file, 'w') as f:
        f.write("=== Migration Validation Report ===\n")
        f.write(f"Date: {results['timestamp']}\n\n")
        
        f.write("=== Summary ===\n")
        for category, data in results['summary'].items():
            if isinstance(data, dict) and 'total' in data:
                f.write(f"{category.replace('_', ' ').title()}: {data['valid']}/{data['total']} valid\n")
            else:
                f.write(f"{category.replace('_', ' ').title()}: {json.dumps(data, indent=2)}\n")
        
        f.write("\n=== Details ===\n")
        for category, errors in results['details'].items():
            if errors:
                f.write(f"\n{category.replace('_', ' ').title()}:\n")
                for error in errors:
                    f.write(f"- {json.dumps(error, indent=2)}\n")
    
    print(f"\nDetailed report saved to {report_file}")