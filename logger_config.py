# logger_config.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

logger_path = "logs/jarvis_process.log"
if getattr(sys, 'frozen', False):
    logger_path = os.path.join(sys._MEIPASS, "logs/jarvis_process.log")

# Set up a logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    handlers=[logging.FileHandler(logger_path), logging.StreamHandler()])

handler = RotatingFileHandler(logger_path, maxBytes=1024*10, backupCount=3)

logging.getLogger().addHandler(handler)


def get_logger():
    """
    Sets up the jarvis_process.log

    :return: The logger.
    :rtype: logging.Logger
    """
    return logging.getLogger(__name__)
