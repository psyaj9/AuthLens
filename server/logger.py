import logging
from pathlib import Path

def setup_logger(name: str, log_file: str | Path, level=logging.DEBUG):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger("authlens", Path(__file__).with_name("app.log"))
