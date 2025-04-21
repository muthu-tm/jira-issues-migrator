# Jira Migration Toolkit

A complete Python solution for migrating Jira projects with all related data including issues, comments, attachments, and metadata.

## Features

- **Complete Migration**: Issues, comments, attachments, and metadata
- **Field Mapping**: Customizable mappings for users, statuses, issue types, etc.
- **Validation**: Comprehensive post-migration validation
- **Error Handling**: Detailed error tracking and retry capability
- **Test Mode**: Safe dry-run capability
- **Reporting**: Detailed migration and validation reports

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-repo/jira-migrator.git
   cd jira-migrator

2. Set up virtual environment:
    ```
    bash
    python -m venv venv
    source venv/bin/activate  # Linux/Mac
    # or venv\Scripts\activate on Windows

3. Install dependencies:
    ```
    bash
    pip install -r requirements.txt

4. Configuration:

- Copy .env.example to .env and fill in your Jira credentials

- Configure config/mapping_config.json with your field mappings

## Usage

1. Fetch Data from Source Jira
    ```
    bash
    make fetch-issues

2. Full Migration
    ```
    bash
    make migrate-all

3. Individual Components
    ```
    bash
    # Migrate only issues
    make migrate-issues

    # Migrate only comments
    make migrate-comments

    # Migrate only attachments
    make migrate-attachments

4. Test Migrations (Dry Run)
    ```
    bash
    # Test migration with 5 sample issues
    make test-migrate-all

    # Test specific components
    make test-migrate-issues
    make test-migrate-comments
    make test-migrate-attachments

5. Limited Migrations
    ```
    bash
    # Migrate first 50 items only
    make limited-migrate-all
    make limited-migrate-issues

6. Retry Failed Migrations
    ```
    bash
    # Retry all failed migrations
    make retry-all

    # Retry specific failed components
    make retry-issues
    make retry-comments
    make retry-attachments

    # With custom retry limit (default: 3)
    python -m src.retry_handler --issues --retries=5

7. Validation
    ```
    bash
    # Full validation
    make validate

    # Individual validation components
    make validate-counts
    make validate-mappings
    make validate-content
    make validate-comments
    make validate-attachments

    # Sample validation (5 issues)
    make sample-validate

8. Cleanup
    ```
    bash
    # Clean error logs
    make clean-logs

    # Full cleanup
    make clean-all

## Advanced Usage Examples

1. Complex Migration with Validation
    ```
    bash
    # Step 1: Fetch data
    make fetch-issues

    # Step 2: Test migration
    make test-migrate-all

    # Step 3: Run actual migration
    make migrate-all

    # Step 4: Validate
    make validate

    # Step 5: Retry any failures
    make retry-all

    # Step 6: Final validation
    make validate

2. Migrating Large Projects
    ```
    bash
    # Migrate in batches
    for i in {1..5}; do
    python -m src.migrator --issues --limit=1000 --offset=$((($i-1)*1000))
    done

    # Then migrate related data
    python -m src.migrator --comments
    python -m src.migrator --attachments

3. Generating Reports
    ```
    bash
    # Generate full validation report
    python -m src.validator --full > validation_report.txt

    # Generate error summary
    cat data/logs/validation_errors.csv | cut -d',' -f1,4 | sort | uniq -c