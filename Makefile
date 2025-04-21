.PHONY: install fetch_issues run_migration run_test_migration migrate_comments migrate_attachments validate test clean

install:
	pip install -r requirements.txt

fetch_issues:
	python -m src.fetcher --all

# Migration Commands
migrate-issues:
	python -m src.migrator --issues

migrate-comments:
	python -m src.migrator --comments

migrate-attachments:
	python -m src.migrator --attachments

migrate-all:
	python -m src.migrator --all

# Test Migration Commands
test-migrate-issues:
	python -m src.migrator --issues --test --limit=10

test-migrate-comments:
	python -m src.migrator --comments --test --limit=5

test-migrate-attachments:
	python -m src.migrator --attachments --test --limit=5

test-migrate-all:
	python -m src.migrator --all --test --limit=5

# Limited Migration Commands
limited-migrate-issues:
	python -m src.migrator --issues --limit=50

limited-migrate-comments:
	python -m src.migrator --comments --limit=50

limited-migrate-attachments:
	python -m src.migrator --attachments --limit=50

limited-migrate-all:
	python -m src.migrator --all --limit=50

# Retry Commands
retry-issues:
	python -m src.retry_handler --issues

retry-comments:
	python -m src.retry_handler --comments

retry-attachments:
	python -m src.retry_handler --attachments

retry-all:
	python -m src.retry_handler --all

# Validation Commands
validate:
	python -m src.validator --full

validate-counts:
	python -m src.validator --counts

validate-mappings:
	python -m src.validator --mappings

validate-content:
	python -m src.validator --content

validate-comments:
	python -m src.validator --comments

validate-attachments:
	python -m src.validator --attachments

# Sample validation (smaller subset)
sample-validate:
	python -m src.validator --full --sample=5

# Cleanup Commands
clean-logs:
	python -m src.cleanup --logs

clean-all:
	python -m src.cleanup --all