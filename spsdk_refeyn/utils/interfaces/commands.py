#!/usr/bin/env python
# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------

"""Generic commands implementation."""

from abc import ABC, abstractmethod


class CmdResponseBase(ABC):
    """Response base format class."""

    @abstractmethod
    def __str__(self) -> str:
        """Get object info."""

    @property
    @abstractmethod
    def value(self) -> int:
        """Return a integer representation of the response."""


class CmdPacketBase(ABC):
    """COmmand protocol base."""

    @abstractmethod
    def to_bytes(self, padding: bool = True) -> bytes:
        """Serialize CmdPacket into bytes.

        :param padding: If True, add padding to specific size
        :return: Serialized object into bytes
        """
