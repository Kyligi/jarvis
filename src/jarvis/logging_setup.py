"""Logs JSON sans commandes, paramètres, résultats ni messages d'exception."""
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "command_id": getattr(record, "command_id", None),
            "error_type": getattr(record, "error_type", None),
        }, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("jarvis")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
