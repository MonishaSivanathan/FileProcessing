import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "application.log"


class AppOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith("app.")


def setup_logging(level: int = logging.INFO) -> Path:
    if getattr(setup_logging, "_configured", False):
        return LOG_FILE

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_format = (
        "%(asctime)s | %(levelname)s | %(name)s | %(funcName)s | %(message)s"
    )
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(AppOnlyFilter())
    root_logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(AppOnlyFilter())
    root_logger.addHandler(file_handler)

    # Let framework loggers propagate, but handler filters keep only app.* logs.
    for logger_name in ("flask.app", "werkzeug", "azure"):
        framework_logger = logging.getLogger(logger_name)
        framework_logger.handlers = []
        framework_logger.setLevel(level)
        framework_logger.propagate = True

    setup_logging._configured = True
    return LOG_FILE


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
