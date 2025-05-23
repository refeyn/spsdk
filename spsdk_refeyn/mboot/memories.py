#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2016-2018 Martin Olejar
# Copyright 2019-2024 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

"""Various types of memory identifiers used in the MBoot module."""

from spsdk_refeyn.utils.misc import size_fmt
from spsdk_refeyn.utils.spsdk_enum import SpsdkEnum

LEGACY_MEM_ID = {
    "internal": "INTERNAL",
    "qspi": "QSPI",
    "fuse": "FUSE",
    "ifr": "IFR0",
    "semcnor": "SEMC_NOR",
    "flexspinor": "FLEX-SPI-NOR",
    "semcnand": "SEMC-NAND",
    "spinand": "SPI-NAND",
    "spieeprom": "SPI-MEM",
    "i2ceeprom": "I2C-MEM",
    "sdcard": "SD",
    "mmccard": "MMC",
}


########################################################################################################################
# McuBoot External Memory ID
########################################################################################################################


########################################################################################################################
# McuBoot External Memory Property Tags
########################################################################################################################


class ExtMemPropTags(SpsdkEnum):
    """McuBoot External Memory Property Tags."""

    INIT_STATUS = (0x00000000, "INIT_STATUS")
    START_ADDRESS = (0x00000001, "START_ADDRESS")
    SIZE_IN_KBYTES = (0x00000002, "SIZE_IN_KBYTES")
    PAGE_SIZE = (0x00000004, "PAGE_SIZE")
    SECTOR_SIZE = (0x00000008, "SECTOR_SIZE")
    BLOCK_SIZE = (0x00000010, "BLOCK_SIZE")


class MemoryRegion:
    """Base class for memory regions."""

    def __init__(self, start: int, end: int) -> None:
        """Initialize the memory region object.

        :param start: start address of region
        :param end: end address of region

        """
        self.start = start
        self.end = end
        self.size = end - start + 1

    def __repr__(self) -> str:
        return f"Memory region, start: {hex(self.start)}"

    def __str__(self) -> str:
        return (
            f"0x{self.start:08X} - 0x{self.end:08X}; Total Size: {size_fmt(self.size)}"
        )
