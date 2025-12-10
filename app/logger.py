import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
import pathlib


LOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "workflow.log"

# Create base logger
logger = logging.getLogger("workflow_engine")
logger.setLevel(logging.INFO)

# Rotating file handler (5MB max per file, keep 3 old files)
file_handler = RotatingFileHandler(
    LOG_PATH, maxBytes=5_000_000, backupCount=3
)

# JSON formatter for structured logs
json_formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)

file_handler.setFormatter(json_formatter)

# Add the handler to the logger
logger.addHandler(file_handler)

# Optional: also log to console for debugging
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(console_handler)

# Expose logger for use elsewhere
workflow_logger = logger
