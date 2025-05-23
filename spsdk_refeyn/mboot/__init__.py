#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2016-2018 Martin Olejar
# Copyright 2019-2025 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

"""Module implementing communication with the MCU Bootloader."""

from typing import Union

from spsdk_refeyn.mboot.interfaces.uart import MbootUARTInterface
from spsdk_refeyn.mboot.interfaces.usb import MbootUSBInterface

MbootDeviceTypes = Union[
    MbootUARTInterface,
    MbootUSBInterface,
]
