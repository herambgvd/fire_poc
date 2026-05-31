import logging
from PyQt6.QtCore import QObject, pyqtSignal

class LogSignals(QObject):
    new_log = pyqtSignal(str, str)  # level, formatted_message

class GuiLogHandler(logging.Handler):
    """
    Custom logging handler that emits PyQt signals.
    Thread-safe way to pipe standard Python logs to the GUI.
    """
    def __init__(self):
        super().__init__()
        self.signals = LogSignals()
        self.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signals.new_log.emit(record.levelname, msg)
        except Exception:
            self.handleError(record)

# Global singleton so dashboard can connect to it easily
gui_log_handler = GuiLogHandler()
