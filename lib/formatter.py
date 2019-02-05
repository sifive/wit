
import logging

class WitFormatter(logging.Formatter):
    """
    Custom formatter to prefix messages except for log.info
    """

    info_format = "%(msg)s"

    def __init__(self):
        super().__init__(fmt="[%(levelname)s] %(msg)s", datefmt=None, style='%')

    def format(self, record):

        orig_fmt = self._style._fmt
        if record.levelno == logging.INFO:
            self._style._fmt = WitFormatter.info_format

        result = logging.Formatter.format(self, record)
        self._style._fmt = orig_fmt

        return result
