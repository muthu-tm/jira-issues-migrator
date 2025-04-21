import argparse
import json
import os
import requests
from tqdm import tqdm
from datetime import datetime
from config.settings import settings
from src.utils import make_auth, ensure_dir
from src.logger import logger

class JiraFetcher:
    def __init__(self):
        ensure_dir(settings.EXPORT_DIR)
        self.export_file = os.path.join(
            settings.EXPORT_DIR, 
            f"{settings.SOURCE_PROJECT_KEY}_issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        self.stats = {
            'total_issues': 0,
            'with_comments': 0,
            'with_attachments': 0,
            'fetch_time': None
        }

    def fetch_all_issues(self):
        """Fetch all issues from source Jira project with pagination"""
        logger.info(f"Starting issue export from project {settings.SOURCE_PROJECT_KEY}")
        start_time = datetime.now()
        
        all_issues = []
        start_at = 0
        max_results = 100  # Optimal batch size
        total_issues = self._get_total_issue_count()
        
        if total_issues == 0:
            logger.error("No issues found in source project")
            return None

        logger.info(f"Found {total_issues} issues to export")
        self.stats['total_issues'] = total_issues

        with tqdm(total=total_issues, desc="Exporting issues") as pbar:
            while start_at < total_issues:
                batch = self._fetch_issue_batch(start_at, max_results)
                if not batch:
                    break
                
                all_issues.extend(batch)
                start_at += len(batch)
                pbar.update(len(batch))
                
                # Update stats
                self._update_batch_stats(batch)

        # Save results
        result = {
            'metadata': {
                'source_project': settings.SOURCE_PROJECT_KEY,
                'export_date': datetime.now().isoformat(),
                'stats': self.stats
            },
            'issues': all_issues
        }

        with open(self.export_file, 'w') as f:
            json.dump(result, f, indent=2)

        self.stats['fetch_time'] = str(datetime.now() - start_time)
        logger.info(f"Successfully exported {len(all_issues)} issues to {self.export_file}")
        logger.info(f"Export stats: {json.dumps(self.stats, indent=2)}")
        
        return self.export_file

    def _get_total_issue_count(self):
        """Get total number of issues in project"""
        jql = f"project={settings.SOURCE_PROJECT_KEY}"
        url = f"{settings.SOURCE_JIRA_URL}/rest/api/2/search?jql={jql}&maxResults=0"
        
        try:
            response = requests.get(
                url,
                auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                timeout=30
            )
            return response.json().get('total', 0) if response.status_code == 200 else 0
        except Exception as e:
            logger.error(f"Failed to get issue count: {str(e)}")
            return 0

    def _fetch_issue_batch(self, start_at, max_results):
        """Fetch a batch of issues with expanded fields"""
        url = (
            f"{settings.SOURCE_JIRA_URL}/rest/api/2/search?"
            f"jql=project={settings.SOURCE_PROJECT_KEY}&"
            f"startAt={start_at}&maxResults={max_results}&"
            "expand=renderedFields,names,operations,editmeta,changelog,versionedRepresentations,attachment,comments"
        )
        
        try:
            response = requests.get(
                url,
                auth=make_auth(settings.SOURCE_USERNAME, settings.SOURCE_PASSWORD),
                timeout=60
            )
            if response.status_code == 200:
                return response.json().get('issues', [])
            logger.error(f"Failed to fetch batch: {response.text}")
            return []
        except Exception as e:
            logger.error(f"Error fetching batch: {str(e)}")
            return []

    def _update_batch_stats(self, batch):
        """Update statistics with current batch data"""
        for issue in batch:
            if issue['fields'].get('comment', {}).get('comments', []):
                self.stats['with_comments'] += 1
            if issue['fields'].get('attachment', []):
                self.stats['with_attachments'] += 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', help='Fetch all issues')
    parser.add_argument('--project', help='Override source project key')
    args = parser.parse_args()
    
    if args.project:
        settings.SOURCE_PROJECT_KEY = args.project
    
    if args.all:
        fetcher = JiraFetcher()
        export_file = fetcher.fetch_all_issues()
        if export_file:
            print(f"Issues exported to: {export_file}")

if __name__ == "__main__":
    main()