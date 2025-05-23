#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2019-2024 NXP
#
#
# SPDX-License-Identifier: BSD-3-Clause

"""Module implementing the SDPS communication protocol."""

import logging
from struct import pack

from spsdk.utils.interfaces.commands import CmdPacketBase
from spsdk.utils.misc import swap32
from spsdk.utils.spsdk_enum import SpsdkEnum

logger = logging.getLogger(__name__)


class CommandFlag(SpsdkEnum):
    """Command flag enum."""

    DEVICE_TO_HOST_DIR = (0x80, "DataOut", "Data Out")
    HOST_TO_DEVICE_DIR = (0x00, "DataIn", "Data In")


class CommandTag(SpsdkEnum):
    """Command tag enum."""

    FW_DOWNLOAD = (2, "FwDownload", "Firmware download")


class CmdPacket(CmdPacketBase):
    """Class representing a command packet to be sent to device."""

    FORMAT = "<3IB2xbI11x"

    def __init__(
        self,
        signature: int,
        length: int,
        flags: CommandFlag,
        command: CommandTag,
        tag: int = 1,
    ):
        """Initialize the struct.

        :param tag: Tag number representing the command
        :param address: Address used by the command
        :param pformat: Format of the data: 8 = byte, 16 = half-word, 32 = word
        :param count: Count used by individual command
        :param value: Value to use in a particular command, defaults to 0
        """
        self.signature = signature
        self.tag = tag
        self.length = length
        self.flags = flags
        self.cdb_command = command

    def __str__(self) -> str:
        """String representation of the command packet."""
        return (
            f"Signature={self.signature}, Tag=0x{self.tag},"
            f" Length={self.length}, Flags={self.flags}, CdbCommand=0x{self.cdb_command}"
        )

    def to_bytes(self, padding: bool = True) -> bytes:
        """Return command packet as bytes."""
        return pack(
            self.FORMAT,
            self.signature,
            self.tag,
            self.length,
            self.flags.tag,
            self.cdb_command.tag,
            swap32(self.length),
        )
