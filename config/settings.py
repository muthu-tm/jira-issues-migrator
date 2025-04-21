import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Source Jira
    SOURCE_JIRA_URL = os.getenv('SOURCE_JIRA_URL')
    SOURCE_USERNAME = os.getenv('SOURCE_USERNAME')
    SOURCE_PASSWORD = os.getenv('SOURCE_PASSWORD')
    
    # Target Jira
    TARGET_JIRA_URL = os.getenv('TARGET_JIRA_URL')
    TARGET_USERNAME = os.getenv('TARGET_USERNAME')
    TARGET_PASSWORD = os.getenv('TARGET_PASSWORD')
    
    # Project mapping
    SOURCE_PROJECT_KEY = os.getenv('SOURCE_PROJECT_KEY')
    TARGET_PROJECT_KEY = os.getenv('TARGET_PROJECT_KEY')
    
    # Paths
    EXPORT_DIR = 'data/exported/'
    LOG_DIR = 'data/logs/'
    
    # Default user for unmapped users
    DEFAULT_USER = os.getenv('DEFAULT_USER', 'admin@example.com')

settings = Settings()