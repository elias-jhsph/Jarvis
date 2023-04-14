# logger_config.py
import logging
from logging.handlers import RotatingFileHandler


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    handlers=[logging.FileHandler("logs/jarvis_process.log"), logging.StreamHandler()])

handler = RotatingFileHandler('logs/jarvis_process.log', maxBytes=1024*10, backupCount=3)

logging.getLogger().addHandler(handler)


def get_logger():
    """
    Sets up the jarvis_process.log
    """
    return logging.getLogger(__name__)
