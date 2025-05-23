#!/usr/bin/env python
# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------

"""Miscellaneous functions used throughout the SPSDK."""

import hashlib
import json
import logging
import os
import re
import time
from enum import Enum
from math import ceil
from struct import pack, unpack
from typing import Callable, Iterable, Optional, TypeVar, Union

from packaging.version import Version, parse

from spsdk.exceptions import SPSDKError, SPSDKValueError
from spsdk.utils.exceptions import SPSDKTimeoutError

# for generics
T = TypeVar("T")  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)


class Endianness(str, Enum):
    """Endianness enum."""

    BIG = "big"
    LITTLE = "little"

    @classmethod
    def values(cls) -> list[str]:
        """Get enumeration values."""
        return [mem.value for mem in Endianness.__members__.values()]


class BinaryPattern:
    """Binary pattern class.

    Supported patterns:
        - rand: Random Pattern
        - zeros: Filled with zeros
        - ones: Filled with all ones
        - inc: Filled with repeated numbers incremented by one 0-0xff
        - any kind of number, that will be repeated to fill up whole image.
          The format could be decimal, hexadecimal, bytes.
    """

    SPECIAL_PATTERNS = ["rand", "zeros", "ones", "inc"]

    def __init__(self, pattern: str) -> None:
        """Constructor of pattern class.

        :param pattern: Supported patterns:
                        - rand: Random Pattern
                        - zeros: Filled with zeros
                        - ones: Filled with all ones
                        - inc: Filled with repeated numbers incremented by one 0-0xff
                        - any kind of number, that will be repeated to fill up whole image.
                        The format could be decimal, hexadecimal, bytes.
        :raises SPSDKValueError: Unsupported pattern detected.
        """
        try:
            value_to_int(pattern)
        except SPSDKError:
            if pattern not in BinaryPattern.SPECIAL_PATTERNS:
                raise SPSDKValueError(  # pylint: disable=raise-missing-from
                    f"Unsupported input pattern {pattern}"
                )

        self._pattern = pattern

    @property
    def pattern(self) -> str:
        """Get the pattern.

        :return: Pattern in string representation.
        """
        try:
            return hex(value_to_int(self._pattern))
        except SPSDKError:
            return self._pattern


def find_first(iterable: Iterable[T], predicate: Callable[[T], bool]) -> Optional[T]:
    """Find first element from the list, that matches the condition.

    :param iterable: list of elements
    :param predicate: function for selection of the element
    :return: found element; None if not found
    """
    return next((a for a in iterable if predicate(a)), None)


def load_text(path: str, search_paths: Optional[list[str]] = None) -> str:
    """Loads text file into string.

    :param path: Path to the file.
    :param search_paths: List of paths where to search for the file, defaults to None
    :return: content of the text file as string
    """
    text = load_file(path, mode="r", search_paths=search_paths)
    assert isinstance(text, str)
    return text


def load_file(
    path: str, mode: str = "r", search_paths: Optional[list[str]] = None
) -> Union[str, bytes]:
    """Loads a file into bytes.

    :param path: Path to the file.
    :param mode: mode for reading the file 'r'/'rb'
    :param search_paths: List of paths where to search for the file, defaults to None
    :return: content of the binary file as bytes or str (based on mode)
    """
    path = find_file(path, search_paths=search_paths)
    logger.debug(f"Loading {'binary' if 'b' in mode else 'text'} file from {path}")
    encoding = None if "b" in mode else "utf-8"
    with open(path, mode, encoding=encoding) as f:
        return f.read()  # type: ignore[no-any-return]


def write_file(
    data: Union[str, bytes], path: str, mode: str = "w", encoding: str = "utf-8"
) -> int:
    """Writes data into a file.

    :param data: data to write
    :param path: Path to the file.
    :param mode: writing mode, 'w' for text, 'wb' for binary data, defaults to 'w'
    :param encoding: Encoding of written file ('ascii', 'utf-8'), default is 'utf-8'.
    :return: number of written elements
    """
    path = path.replace("\\", "/")
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    logger.debug(f"Storing {'binary' if 'b' in mode else 'text'} file at {path}")
    with open(path, mode, encoding=None if "b" in mode else encoding) as f:
        return f.write(data)


def get_abs_path(file_path: str, base_dir: Optional[str] = None) -> str:
    """Return a full path to the file.

    param base_dir: Base directory to create absolute path, if not specified the system CWD is used.
    return: Absolute file path.
    """
    if os.path.isabs(file_path):
        return file_path.replace("\\", "/")

    return os.path.abspath(os.path.join(base_dir or os.getcwd(), file_path)).replace(
        "\\", "/"
    )


def _find_path(
    path: str,
    check_func: Callable[[str], bool],
    use_cwd: bool = True,
    search_paths: Optional[list[str]] = None,
    raise_exc: bool = True,
) -> str:
    """Return a full path to the file.

    `search_paths` takes precedence over `CWD` if used (default)

    :param path: File name, part of file path or full path
    :param use_cwd: Try current working directory to find the file, defaults to True
    :param search_paths: List of paths where to search for the file, defaults to None
    :param raise_exc: Raise exception if file is not found, defaults to True
    :return: Full path to the file
    :raises SPSDKError: File not found
    """
    path = path.replace("\\", "/")

    if os.path.isabs(path):
        if not check_func(path):
            if raise_exc:
                raise SPSDKError(f"Path '{path}' not found")
            return ""
        return path
    if search_paths:
        for dir_candidate in search_paths:
            if not dir_candidate:
                continue
            dir_candidate = dir_candidate.replace("\\", "/")
            path_candidate = get_abs_path(path, base_dir=dir_candidate)
            if check_func(path_candidate):
                return path_candidate
    if use_cwd and check_func(path):
        return get_abs_path(path)
    # list all directories in error message
    searched_in: list[str] = []
    if use_cwd:
        searched_in.append(os.path.abspath(os.curdir))
    if search_paths:
        searched_in.extend(filter(None, search_paths))
    searched_in = [s.replace("\\", "/") for s in searched_in]
    err_str = f"Path '{path}' not found, Searched in: {', '.join(searched_in)}"
    if not raise_exc:
        logger.debug(err_str)
        return ""
    raise SPSDKError(err_str)


def find_file(
    file_path: str,
    use_cwd: bool = True,
    search_paths: Optional[list[str]] = None,
    raise_exc: bool = True,
) -> str:
    """Return a full path to the file.

    `search_paths` takes precedence over `CWD` if used (default)

    :param file_path: File name, part of file path or full path
    :param use_cwd: Try current working directory to find the file, defaults to True
    :param search_paths: List of paths where to search for the file, defaults to None
    :param raise_exc: Raise exception if file is not found, defaults to True
    :return: Full path to the file
    :raises SPSDKError: File not found
    """
    return _find_path(
        path=file_path,
        check_func=os.path.isfile,
        use_cwd=use_cwd,
        search_paths=search_paths,
        raise_exc=raise_exc,
    )


def value_to_int(
    value: Union[bytes, bytearray, int, str], default: Optional[int] = None
) -> int:
    """Function loads value from lot of formats to integer.

    :param value: Input value.
    :param default: Default Value in case of invalid input.
    :return: Value in Integer.
    :raises SPSDKError: Unsupported input type.
    """
    if isinstance(value, int):
        return value

    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, Endianness.BIG.value)

    if isinstance(value, str) and value != "":
        match = re.match(
            r"(?P<prefix>0[box])?(?P<number>[0-9a-f_]+)(?P<suffix>[ul]{0,3})$",
            value.strip().lower(),
        )
        if match:
            base = {"0b": 2, "0o": 8, "0": 10, "0x": 16, None: 10}[
                match.group("prefix")
            ]
            try:
                return int(match.group("number"), base=base)
            except ValueError:
                pass

    if default is not None:
        return default
    raise SPSDKError(f"Invalid input number type({type(value)}) with value ({value})")


def value_to_bool(value: Optional[Union[bool, int, str]]) -> bool:
    """Function decode bool value from various formats.

    :param value: Input value.
    :return: Boolean value.
    :raises SPSDKError: Unsupported input type.
    """
    if isinstance(value, str):
        return value in ("True", "true", "T", "1")

    return bool(value)


class Timeout:
    """Simple timeout handle class."""

    UNITS = {
        "s": 1000000,
        "ms": 1000,
        "us": 1,
    }

    def __init__(self, timeout: int, units: str = "s") -> None:
        """Simple timeout class constructor.

        :param timeout: Timeout value.
        :param units: Timeout units (MUST be from the UNITS list)
        :raises SPSDKValueError: Invalid input value.
        """
        if units not in self.UNITS:
            raise SPSDKValueError("Units are not in supported units.")
        self.enabled = timeout != 0
        self.timeout_us = timeout * self.UNITS[units]
        self.start_time_us = self._get_current_time_us()
        self.end_time = self.start_time_us + self.timeout_us
        self.units = units

    @staticmethod
    def _get_current_time_us() -> int:
        """Returns current system time in microseconds.

        :return: Current time in microseconds
        """
        return ceil(time.time() * 1_000_000)

    def overflow(self, raise_exc: bool = False) -> bool:
        """Check the the timer has been overflowed.

        :param raise_exc: If set, the function raise SPSDKTimeoutError in case of overflow.
        :return: True if timeout overflowed, False otherwise.
        :raises SPSDKTimeoutError: In case of overflow
        """
        overflow = self.enabled and self._get_current_time_us() > self.end_time
        if overflow and raise_exc:
            raise SPSDKTimeoutError("Timeout of operation.")
        return overflow


def size_fmt(num: Union[float, int], use_kibibyte: bool = True) -> str:
    """Size format."""
    base, suffix = [(1000.0, "B"), (1024.0, "iB")][use_kibibyte]
    i = "B"
    for i in ["B"] + [i + suffix for i in list("kMGTP")]:
        if num < base:
            break
        num /= base

    return f"{int(num)} {i}" if i == "B" else f"{num:3.1f} {i}"


def swap32(x: int) -> int:
    """Swap 32 bit integer.

    :param x: integer to be swapped
    :return: swapped value
    :raises SPSDKError: When incorrect number to be swapped is provided
    """
    if x < 0 or x > 0xFFFFFFFF:
        raise SPSDKError("Incorrect number to be swapped")
    return unpack("<I", pack(">I", x))[0]  # type: ignore[no-any-return]


def load_configuration(path: str, search_paths: Optional[list[str]] = None) -> dict:
    """Load configuration from yml/json file.

    :param path: Path to configuration file
    :param search_paths: List of paths where to search for the file, defaults to None
    :raises SPSDKError: When unsupported file is provided
    :return: Content of configuration as dictionary
    """
    try:
        config = load_text(path, search_paths=search_paths)
    except Exception as exc:
        raise SPSDKError(f"Can't load configuration file: {str(exc)}") from exc

    config_data: Optional[dict] = None
    try:
        config_data = json.loads(config)
    except json.JSONDecodeError:
        # import YAML only if needed to save startup time
        from yaml import YAMLError, safe_load  # pylint: disable=import-outside-toplevel

        try:
            config_data = safe_load(config)
        except (YAMLError, UnicodeDecodeError):
            pass

    if not config_data:
        raise SPSDKError(f"Can't parse configuration file: {path}")
    if not isinstance(config_data, dict):
        raise SPSDKError(f"Invalid configuration file: {path}")

    return config_data


def get_hash(text: Union[str, bytes]) -> str:
    """Returns hash of given text."""
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).digest().hex()[:8]


def deep_update(d: dict, u: dict) -> dict:
    """Deep update nested dictionaries.

    :param d: Dictionary that will be updated
    :param u: Dictionary with update information
    :returns: Updated dictionary.
    """
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def get_spsdk_version() -> Version:
    """Get SPSDK version."""
    try:
        from spsdk.__version__ import version as spsdk_version

    except ImportError:
        # from setuptools_scm import get_version

        # spsdk_version = get_version()
        ...
    return parse(spsdk_version)
