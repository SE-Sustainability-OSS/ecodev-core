"""
Helpers for pretty logging
"""
import logging
import sys
import traceback


def log_critical(message: str, logger):
    """
    Traceback enabled for unintended serious errors
    """
    logger.error(message)
    logger.error(traceback.format_exc())


def logger_get(name, level=logging.DEBUG):
    """
    Main method called by all other modules to log
    """
    logger = logging.getLogger(name)
    config_log(logger, level, MyFormatter())
    return logger


class MyFormatter(logging.Formatter):
    """
    Formatter to print %(filename)s:%(funcName)s:%(lineno)d on 24 characters

    Typical format :
    2016-10-26 14:20:21,379 | DEBUG    | logger:log_me:57         : This is a log
    """
    message_width = 110
    cpath_width = 32
    date_fmt = '%Y-%m-%d %H:%M:%S'

    pink = '\x1b[35m'
    green = '\x1b[32m'
    yellow = '\x1b[33m'
    red = '\x1b[31m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'

    FORMATS = {
        logging.DEBUG: pink,
        logging.INFO: green,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red,
    }

    def format(self, record):
        """
        Format logs
        """
        initial_record = f'{record.module}:{record.funcName}:{ record.lineno}'
        cpath = initial_record[-self.cpath_width:].ljust(self.cpath_width)
        time = self.formatTime(record, self.date_fmt)
        prefix = f'{time} | {record.levelname} | {record.process} | {cpath}'

        # fixing max length
        limited_lines = []
        for line in record.getMessage().split(str('\n')):
            while len(line) > self.message_width:
                if (last_space_position := line[:self.message_width - 1].rfind(' ')) > 0:
                    splitting_position = last_space_position
                else:
                    splitting_position = self.message_width
                limited_lines.append(line[:splitting_position])
                line = line[splitting_position:]

            # don't forget end of line
            limited_lines.append(line)

        # formatting final message
        final_message = ''.join(f'{prefix} | {line}\n' for line in limited_lines).rstrip()

        return f'{self.FORMATS[record.levelno]}{final_message}{self.reset}'


def config_log(logger, level, formatter):
    """ Configures the logging.

    This function defines the root logger. It needs to be called only once.
    Then, all modules should log like this:
    '''
    from logger.logger import get as logger_get
    log = logger_get(__name__)
    '''
    If the function is called more than once, duplicate handlers are ignored
    to avoid duplicate logging.

    Args:
        logger: logging object
        level: Logging level
        formatter: Logging format

    """
    # Get the root logger (because no name is specified in getLogger())
    logger.setLevel(level)
    logger.propagate = False

    console_handler = logging.StreamHandler(stream=sys.stdout)
    if all(handler.stream.name != console_handler.stream.name for handler in logger.handlers):
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
