#!/usr/bin/env python
# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------

"""Protocol base."""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type, Union

from typing_extensions import Self

from spsdk_refeyn.utils.interfaces.commands import CmdPacketBase, CmdResponseBase
from spsdk_refeyn.utils.interfaces.device.base import DeviceBase


class ProtocolBase(ABC):
    """Protocol base class."""

    device: DeviceBase
    identifier: str

    def __init__(self, device: DeviceBase) -> None:
        """Initialize the MbootSerialProtocol object.

        :param device: The device instance
        """
        self.device = device

    def __str__(self) -> str:
        return f"identifier='{self.identifier}', device={self.device}"

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exception_type: Optional[Type[Exception]] = None,
        exception_value: Optional[Exception] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        self.close()

    @abstractmethod
    def open(self) -> None:
        """Open the interface."""

    @abstractmethod
    def close(self) -> None:
        """Close the interface."""

    @property
    @abstractmethod
    def is_opened(self) -> bool:
        """Indicates whether interface is open."""

    @abstractmethod
    def write_command(self, packet: CmdPacketBase) -> None:
        """Write command to the device.

        :param packet: Command packet to be sent
        """

    @abstractmethod
    def write_data(self, data: bytes) -> None:
        """Write data to the device.

        :param data: Data to be send
        """

    @abstractmethod
    def read(self, length: Optional[int] = None) -> Union[CmdResponseBase, bytes]:
        """Read data from device.

        :return: read data
        """

    @classmethod
    def _get_subclasses(
        cls,
        base_class: Type,
    ) -> list[Type[Self]]:
        """Recursively find all subclasses."""
        subclasses = []
        for subclass in base_class.__subclasses__():
            subclasses.append(subclass)
            subclasses.extend(cls._get_subclasses(subclass))
        return subclasses
