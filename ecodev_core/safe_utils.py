"""
Unittest wrapper ensuring safe setUp / tearDown of all tests.
This boilerplate code is not to be touched under any circumstances.
"""
import contextlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable
from typing import List
from typing import Union
from unittest import TestCase

import numpy as np
from pydantic import Field

from ecodev_core.logger import log_critical
from ecodev_core.logger import logger_get
from ecodev_core.pydantic_utils import Frozen


log = logger_get(__name__)


class SafeTestCase(TestCase):
    """
    SafeTestCase makes sure that setUp / tearDown methods are always run when they should be.
    This boilerplate code is not to be touched under any circumstances.
    """
    files_created: List[Path]
    directories_created: List[Path]

    @classmethod
    def setUpClass(cls) -> None:
        """
        Class set up, prompt class name and set files and folders to be suppressed at tearDownClass
        """
        log.info(f'Running test module: {cls.__module__.upper()}')
        super().setUpClass()
        cls.directories_created = []
        cls.files_created = []

    @classmethod
    def tearDownClass(cls) -> None:
        """
        Safely suppress all files and directories used for this class
        """
        log.info(f'Done running test module: {cls.__module__.upper()}')
        cls.safe_delete(cls.directories_created, cls.files_created)

    def setUp(self) -> None:
        """
        Test set up, prompt test name and set files and folders to be suppressed at tearDown
        """
        super().setUp()
        log.debug(f'Running test: {self._testMethodName.upper()}')
        self.directories_created: List[Path] = []
        self.files_created: List[Path] = []

    def tearDown(self) -> None:
        """
        Safely suppress all files and directories used for this test
        """
        log.debug(f'Done running test: {self._testMethodName.upper()}')
        self.safe_delete(self.directories_created, self.files_created)

    @classmethod
    def safe_delete(cls, directories_created: List[Path], files_created: List[Path]) -> None:
        """
        Safely suppress all passed files_created and directories_created

        Args:
            directories_created: directories used for the test making the call
            files_created: files_created used for the test making the call
        """
        for directory in directories_created:
            with contextlib.suppress(FileNotFoundError):
                shutil.rmtree(directory)
        for file_path in files_created:
            file_path.unlink(missing_ok=True)

    def run(self, result=None):
        """
        Wrapper around unittest run
        """
        test_method = getattr(self, self._testMethodName)
        wrapped_test = self._cleanup_wrapper(test_method, KeyboardInterrupt)
        setattr(self, self._testMethodName, wrapped_test)
        self.setUp = self._cleanup_wrapper(self.setUp, BaseException)

        return super().run(result)

    def _cleanup_wrapper(self, method, exception):
        """
        Boilerplate code for clean setup and teardown
        """

        def _wrapped(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except exception:
                self.tearDown()
                self.doCleanups()
                raise

        return _wrapped


class SimpleReturn(Frozen):
    """
    Simple output for routes not returning anything
    """
    success: bool = Field(..., description=' True if the treatment went well.')
    error: Union[str, None] = Field(..., description='the error that happened, if any.')

    @classmethod
    def route_success(cls) -> 'SimpleReturn':
        """
        Format DropDocumentReturn if the document was successfully dropped
        """
        return SimpleReturn(success=True, error=None)

    @classmethod
    def route_failure(cls, error: str) -> 'SimpleReturn':
        """
        Format DropDocumentReturn if the document failed to be dropped
        """
        return SimpleReturn(success=False, error=error)


def safe_clt(func):
    """
    Safe execution of typer commands
    """
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
            return SimpleReturn.route_success()
        except Exception as error:
            log_critical(f'something wrong happened: {error}', log)
            return SimpleReturn.route_failure(str(error))
    return inner_function


def stringify(x: Union[str, float]) -> Union[str, None]:
    """
    Safe conversion of a (str, np.nan) value into a (str,None) one
    """
    return _transformify(x, str)


def boolify(x: Union[Any]) -> Union[bool, None]:
    """
    Safe conversion of a (str, np.nan) value into a (str,None) one
    """
    return _transformify(x, _bool_check)


def intify(x: Union[str, float]) -> Union[int, None]:
    """
    Safe conversion of a (int, np.nan) value into a (int,None) one
    """
    return _transformify(x, int)


def floatify(x: Union[str, float]) -> Union[float, None]:
    """
    Safe conversion of a (float, np.nan) value into a (float,None) one
    """
    return _transformify(x, float)


def datify(date: str, date_format: str) -> Union[datetime, None]:
    """
    Safe conversion to a date format
    """
    return _transformify(date, lambda x: datetime.strptime(x, date_format))


def _transformify(x: Union[Any, float], transformation: Callable) -> Union[Any, None]:
    """
    Safe conversion of a (Any, np.nan) value into a (Any,None) one thanks to transformation
    """
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None

    try:
        return transformation(x)

    except ValueError:
        return None


def _bool_check(x: Union[Any, float]):
    """
    Check if the passed element can be cast into a boolean, or the boolean value inferred.
    """
    if isinstance(x, bool):
        return x

    if not isinstance(x, str) or x.lower() not in ['true', 'yes', 'false', 'no']:
        return None

    return x.lower() in ['true', 'yes']
