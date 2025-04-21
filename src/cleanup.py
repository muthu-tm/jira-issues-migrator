import argparse
import os
from config.settings import settings
from src.logger import logger

class CleanupManager:
    def __init__(self):
        self.log_dir = settings.LOG_DIR
        self.error_dir = os.path.join(settings.LOG_DIR, 'errors')

    def clear_error_logs(self):
        """Remove all error log files"""
        logger.info("Clearing error logs")
        for filename in os.listdir(self.error_dir):
            file_path = os.path.join(self.error_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    logger.info(f"Removed {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

    def clear_all_logs(self):
        """Remove all log files"""
        self.clear_error_logs()
        # Add other log cleanup as needed
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--logs', action='store_true', help='Cleanup log files')
    parser.add_argument('--all', action='store_true', help='Cleanup all temporary files')
    args = parser.parse_args()

    cleaner = CleanupManager()
    if args.logs:
        cleaner.clear_error_logs()
    elif args.all:
        cleaner.clear_all_logs()