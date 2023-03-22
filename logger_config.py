# logger_config.py
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] - %(message)s',
                    handlers=[logging.FileHandler("jarvis_process.log"), logging.StreamHandler()])


def get_logger():
    """
    Sets up the jarvis_process.log
    """
    return logging.getLogger(__name__)
