import logging
import os
from datetime import datetime
from config.settings import settings
from src.utils import ensure_dir

def setup_logger():
    """Configure and return a logger instance"""
    ensure_dir(settings.LOG_DIR)
    
    logger = logging.getLogger('jira_migrator')
    logger.setLevel(logging.DEBUG)
    
    # File handler
    log_file = os.path.join(settings.LOG_DIR, f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()