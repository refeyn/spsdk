#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2016-2018 Martin Olejar
# Copyright 2019-2025 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

"""Helper module for more human-friendly interpretation of the target device properties."""

import ctypes
import logging
from copy import deepcopy
from typing import Callable, Optional, Type, Union

from spsdk_refeyn.exceptions import SPSDKKeyError
from spsdk_refeyn.mboot.commands import CommandTag
from spsdk_refeyn.mboot.error_codes import StatusCode
from spsdk_refeyn.mboot.exceptions import McuBootError
from spsdk_refeyn.mboot.memories import ExtMemPropTags, MemoryRegion
from spsdk_refeyn.utils.database import DatabaseManager
from spsdk_refeyn.utils.family import FamilyRevision, get_db
from spsdk_refeyn.utils.misc import Endianness
from spsdk_refeyn.utils.spsdk_enum import SpsdkEnum

logger = logging.getLogger(__name__)


########################################################################################################################
# McuBoot helper functions
########################################################################################################################
def size_fmt(value: Union[int, float], kibibyte: bool = True) -> str:
    """Convert size value into string format.

    :param value: The raw value
    :param kibibyte: True if 1024 Bytes represent 1kB or False if 1000 Bytes represent 1kB
    :return: Stringified value
    """
    base, suffix = [(1000.0, "B"), (1024.0, "iB")][kibibyte]
    x = "B"
    for x in ["B"] + [prefix + suffix for prefix in list("kMGTP")]:
        if -base < value < base:
            break
        value /= base

    return f"{value} {x}" if x == "B" else f"{value:3.1f} {x}"


def int_fmt(value: int, format_str: str) -> str:
    """Get stringified integer representation."""
    if format_str == "size":
        str_value = size_fmt(value)
    elif format_str == "hex":
        str_value = f"0x{value:08X}"
    elif format_str == "dec":
        str_value = str(value)
    elif format_str == "int32":
        str_value = str(ctypes.c_int32(value).value)
    else:
        str_value = format_str.format(value)
    return str_value


########################################################################################################################
# McuBoot helper classes
########################################################################################################################


class Version:
    """McuBoot current and target version type."""

    def __init__(self, *args: Union[str, int], **kwargs: int):
        """Initialize the Version object.

        :raises McuBootError: Argument passed the not str not int
        """
        self.mark = kwargs.get("mark", "K")
        self.major = kwargs.get("major", 0)
        self.minor = kwargs.get("minor", 0)
        self.fixation = kwargs.get("fixation", 0)
        if args:
            if isinstance(args[0], int):
                self.from_int(args[0])
            elif isinstance(args[0], str):
                self.from_str(args[0])
            else:
                raise McuBootError("Value must be 'str' or 'int' type !")

    def __eq__(self, obj: object) -> bool:
        return isinstance(obj, Version) and vars(obj) == vars(self)

    def __ne__(self, obj: object) -> bool:
        return not self.__eq__(obj)

    def __lt__(self, obj: "Version") -> bool:
        return self.to_int(True) < obj.to_int(True)

    def __le__(self, obj: "Version") -> bool:
        return self.to_int(True) <= obj.to_int(True)

    def __gt__(self, obj: "Version") -> bool:
        return self.to_int(True) > obj.to_int(True)

    def __ge__(self, obj: "Version") -> bool:
        return self.to_int(True) >= obj.to_int(True)

    def __repr__(self) -> str:
        return f"<Version(mark={self.mark}, major={self.major}, minor={self.minor}, fixation={self.fixation})>"

    def __str__(self) -> str:
        return self.to_str()

    def from_int(self, value: int) -> None:
        """Parse version data from raw int value.

        :param value: Raw integer input
        """
        mark = (value >> 24) & 0xFF
        self.mark = chr(mark) if 64 < mark < 91 else None  # type: ignore
        self.major = (value >> 16) & 0xFF
        self.minor = (value >> 8) & 0xFF
        self.fixation = value & 0xFF

    def from_str(self, value: str) -> None:
        """Parse version data from string value.

        :param value: String representation input
        """
        mark_major, minor, fixation = value.split(".")
        if len(mark_major) > 1 and mark_major[0] not in "0123456789":
            self.mark = mark_major[0]
            self.major = int(mark_major[1:])
        else:
            self.major = int(mark_major)
        self.minor = int(minor)
        self.fixation = int(fixation)

    def to_int(self, no_mark: bool = False) -> int:
        """Get version value in raw integer format.

        :param no_mark: If True, return value without mark
        :return: Integer representation
        """
        value = self.major << 16 | self.minor << 8 | self.fixation
        mark = 0 if no_mark or self.mark is None else ord(self.mark) << 24  # type: ignore
        return value | mark

    def to_str(self, no_mark: bool = False) -> str:
        """Get version value in readable string format.

        :param no_mark: If True, return value without mark
        :return: String representation
        """
        value = f"{self.major}.{self.minor}.{self.fixation}"
        mark = "" if no_mark or self.mark is None else self.mark
        return f"{mark}{value}"


########################################################################################################################
# McuBoot Properties
########################################################################################################################

# fmt: off
class PropertyTag(SpsdkEnum):
    """McuBoot Properties."""

    LIST_PROPERTIES            = (0x00, 'ListProperties', 'List Properties')
    CURRENT_VERSION            = (0x01, "CurrentVersion", "Current Version")
    AVAILABLE_PERIPHERALS      = (0x02, "AvailablePeripherals", "Available Peripherals")
    FLASH_START_ADDRESS        = (0x03, "FlashStartAddress", "Flash Start Address")
    FLASH_SIZE                 = (0x04, "FlashSize", "Flash Size")
    FLASH_SECTOR_SIZE          = (0x05, "FlashSectorSize", "Flash Sector Size")
    FLASH_BLOCK_COUNT          = (0x06, "FlashBlockCount", "Flash Block Count")
    AVAILABLE_COMMANDS         = (0x07, "AvailableCommands", "Available Commands")
    CRC_CHECK_STATUS           = (0x08, "CrcCheckStatus", "CRC Check Status")
    LAST_ERROR                 = (0x09, "LastError", "Last Error Value")
    VERIFY_WRITES              = (0x0A, "VerifyWrites", "Verify Writes")
    MAX_PACKET_SIZE            = (0x0B, "MaxPacketSize", "Max Packet Size")
    RESERVED_REGIONS           = (0x0C, "ReservedRegions", "Reserved Regions")
    VALIDATE_REGIONS           = (0x0D, "ValidateRegions", "Validate Regions")
    RAM_START_ADDRESS          = (0x0E, "RamStartAddress", "RAM Start Address")
    RAM_SIZE                   = (0x0F, "RamSize", "RAM Size")
    SYSTEM_DEVICE_IDENT        = (0x10, "SystemDeviceIdent", "System Device Identification")
    FLASH_SECURITY_STATE       = (0x11, "FlashSecurityState", "Security State")
    UNIQUE_DEVICE_IDENT        = (0x12, "UniqueDeviceIdent", "Unique Device Identification")
    FLASH_FAC_SUPPORT          = (0x13, "FlashFacSupport", "Flash Fac. Support")
    FLASH_ACCESS_SEGMENT_SIZE  = (0x14, "FlashAccessSegmentSize", "Flash Access Segment Size")
    FLASH_ACCESS_SEGMENT_COUNT = (0x15, "FlashAccessSegmentCount", "Flash Access Segment Count")
    FLASH_READ_MARGIN          = (0x16, "FlashReadMargin", "Flash Read Margin")
    QSPI_INIT_STATUS           = (0x17, "QspiInitStatus", "QuadSPI Initialization Status")
    TARGET_VERSION             = (0x18, "TargetVersion", "Target Version")
    EXTERNAL_MEMORY_ATTRIBUTES = (0x19, "ExternalMemoryAttributes", "External Memory Attributes")
    RELIABLE_UPDATE_STATUS     = (0x1A, "ReliableUpdateStatus", "Reliable Update Status")
    FLASH_PAGE_SIZE            = (0x1B, "FlashPageSize", "Flash Page Size")
    IRQ_NOTIFIER_PIN           = (0x1C, "IrqNotifierPin", "Irq Notifier Pin")
    PFR_KEYSTORE_UPDATE_OPT    = (0x1D, "PfrKeystoreUpdateOpt", "PFR Keystore Update Opt")
    BYTE_WRITE_TIMEOUT_MS      = (0x1E, "ByteWriteTimeoutMs", "Byte Write Timeout in ms")
    FUSE_LOCKED_STATUS         = (0x1F, "FuseLockedStatus", "Fuse Locked Status")
    BOOT_STATUS_REGISTER       = (0x20, "BootStatusRegister", "Boot Status Register")
    FIRMWARE_VERSION           = (0x21, "FirmwareVersion", "Firmware Version")
    FUSE_PROGRAM_VOLTAGE       = (0x22, "FuseProgramVoltage", "Fuse Program Voltage")
    SHE_FLASH_PARTITION        = (0x24, "SheFlashPartition", "Secure Hardware Extension: Flash Partition")
    SHE_BOOT_MODE              = (0x25, "SheBootMode", "Secure Hardware Extension: Boot Mode")
    UNKNOWN                    = (0xFF, "Unknown", "Unknown property")


class PropertyTagKw45xx(SpsdkEnum):
    """McuBoot Properties."""

    VERIFY_ERASE               = (0x0A, "VerifyErase", "Verify Erase")
    BOOT_STATUS_REGISTER       = (0x14, "BootStatusRegister", "Boot Status Register")
    FIRMWARE_VERSION           = (0x15, "FirmwareVersion", "Firmware Version")
    FUSE_PROGRAM_VOLTAGE       = (0x16, "FuseProgramVoltage", "Fuse Program Voltage")

class PropertyTagKw47xx(SpsdkEnum):
    """McuBoot Properties."""

    VERIFY_ERASE               = (0x0A, "VerifyErase", "Verify Erase")
    BOOT_STATUS_REGISTER       = (0x14, "BootStatusRegister", "Boot Status Register")
    FIRMWARE_VERSION           = (0x15, "FirmwareVersion", "Firmware Version")
    FUSE_PROGRAM_VOLTAGE       = (0x22, "FuseProgramVoltage", "Fuse Program Voltage")

class PropertyTagMcxa1xx(SpsdkEnum):
    """McuBoot Properties For mcxa1xx."""

    LIFE_CYCLE_STATE           = (0x11, "LifeCycleState", "Life Cycle State")

class PeripheryTag(SpsdkEnum):
    """Tags representing peripherals."""

    UART      = (0x01, "UART", "UART Interface")
    I2C_SLAVE = (0x02, "I2C-Slave", "I2C Slave Interface")
    SPI_SLAVE = (0x04, "SPI-Slave", "SPI Slave Interface")
    CAN       = (0x08, "CAN", "CAN Interface")
    USB_HID   = (0x10, "USB-HID", "USB HID-Class Interface")
    USB_CDC   = (0x20, "USB-CDC", "USB CDC-Class Interface")
    USB_DFU   = (0x40, "USB-DFU", "USB DFU-Class Interface")
    LIN       = (0x80, "LIN", "LIN Interface")


class FlashReadMargin(SpsdkEnum):
    """Scopes for flash read."""

    NORMAL  = (0, "NORMAL")
    USER    = (1, "USER")
    FACTORY = (2, "FACTORY")


class PfrKeystoreUpdateOpt(SpsdkEnum):
    """Options for PFR updating."""

    KEY_PROVISIONING = (0, "KEY_PROVISIONING", "KeyProvisioning")
    WRITE_MEMORY     = (1, "WRITE_MEMORY", "WriteMemory")
# fmt: on

########################################################################################################################
# McuBoot Properties Values
########################################################################################################################


class PropertyValueBase:
    """Base class for property value."""

    __slots__ = ("tag", "name", "desc")

    def __init__(self, tag: int, name: Optional[str] = None, desc: Optional[str] = None) -> None:
        """Initialize the base of property.

        :param tag: Property tag, see: `PropertyTag`
        :param name: Optional name for the property
        :param desc: Optional description for the property
        """
        self.tag = tag
        self.name = name or PropertyTag.get_label(tag) or ""
        self.desc = desc or PropertyTag.get_description(tag, "")

    def __str__(self) -> str:
        return f"{self.desc} = {self.to_str()}"

    def to_str(self) -> str:
        """Stringified representation of a property.

        Derived classes should implement this function.

        :return: String representation
        :raises NotImplementedError: Derived class has to implement this method
        """
        raise NotImplementedError("Derived class has to implement this method.")


class IntValue(PropertyValueBase):
    """Integer-based value property."""

    __slots__ = (
        "value",
        "_fmt",
    )

    def __init__(self, tag: int, raw_values: list[int], str_format: str = "dec") -> None:
        """Initialize the integer-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        :param str_format: Format to display the value ('dec', 'hex', 'size')
        """
        super().__init__(tag)
        self._fmt = str_format
        self.value = raw_values[0]

    def to_int(self) -> int:
        """Get the raw integer property representation."""
        return self.value

    def to_str(self) -> str:
        """Get stringified property representation."""
        return int_fmt(self.value, self._fmt)


class IntListValue(PropertyValueBase):
    """List of integers property."""

    __slots__ = ("value", "_fmt", "delimiter")

    def __init__(
        self, tag: int, raw_values: list[int], str_format: str = "hex", delimiter: str = ", "
    ) -> None:
        """Initialize the integer-list-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        :param str_format: Format to display the value ('dec', 'hex', 'size')
        :param delimiter: Delimiter for values in a list
        """
        super().__init__(tag)
        self._fmt = str_format
        self.value = raw_values
        self.delimiter = delimiter

    def to_str(self) -> str:
        """Get stringified property representation."""
        values = [int_fmt(v, self._fmt) for v in self.value]
        return f"[{self.delimiter.join(values)}]"


class BoolValue(PropertyValueBase):
    """Boolean-based value property."""

    __slots__ = (
        "value",
        "_true_values",
        "_false_values",
        "_true_string",
        "_false_string",
    )

    def __init__(
        self,
        tag: int,
        raw_values: list[int],
        true_values: tuple[int] = (1,),
        true_string: str = "YES",
        false_values: tuple[int] = (0,),
        false_string: str = "NO",
    ) -> None:
        """Initialize the Boolean-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        :param true_values: Values representing 'True', defaults to (1,)
        :param true_string: String representing 'True, defaults to 'YES'
        :param false_values: Values representing 'False', defaults to (0,)
        :param false_string: String representing 'False, defaults to 'NO'
        """
        super().__init__(tag)
        self._true_values = true_values
        self._true_string = true_string
        self._false_values = false_values
        self._false_string = false_string
        self.value = raw_values[0]

    def __bool__(self) -> bool:
        return self.value in self._true_values

    def to_int(self) -> int:
        """Get the raw integer portion of the property."""
        return self.value

    def to_str(self) -> str:
        """Get stringified property representation."""
        return self._true_string if self.value in self._true_values else self._false_string


class EnumValue(PropertyValueBase):
    """Enumeration value property."""

    __slots__ = ("value", "enum", "_na_msg")

    def __init__(
        self,
        tag: int,
        raw_values: list[int],
        enum: Type[SpsdkEnum],
        na_msg: str = "Unknown Item",
    ) -> None:
        """Initialize the enumeration-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        :param enum: Enumeration to pick from
        :param na_msg: Message to display if an item is not found in the enum
        """
        super().__init__(tag)
        self._na_msg = na_msg
        self.enum = enum
        self.value = raw_values[0]

    def to_int(self) -> int:
        """Get the raw integer portion of the property."""
        return self.value

    def to_str(self) -> str:
        """Get stringified property representation."""
        try:
            return self.enum.get_label(self.value)
        except SPSDKKeyError:
            return f"{self._na_msg}: {self.value}"


class VersionValue(PropertyValueBase):
    """Version property class."""

    __slots__ = ("value",)

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the Version-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.value = Version(raw_values[0])

    def to_int(self) -> int:
        """Get the raw integer portion of the property."""
        return self.value.to_int()

    def to_str(self) -> str:
        """Get stringified property representation."""
        return self.value.to_str()


class DeviceUidValue(PropertyValueBase):
    """Device UID value property."""

    __slots__ = ("value",)

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the Version-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.value = b"".join(
            [int.to_bytes(val, length=4, byteorder=Endianness.LITTLE.value) for val in raw_values]
        )

    def to_int(self) -> int:
        """Get the raw integer portion of the property."""
        return int.from_bytes(self.value, byteorder=Endianness.BIG.value)

    def to_str(self) -> str:
        """Get stringified property representation."""
        return "".join(f"{item:02x}" for item in self.value)


class ReservedRegionsValue(PropertyValueBase):
    """Reserver Regions property."""

    __slots__ = ("regions",)

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the ReserverRegion-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.regions: list[MemoryRegion] = []
        for i in range(0, len(raw_values), 2):
            if raw_values[i + 1] == 0:
                continue
            self.regions.append(MemoryRegion(raw_values[i], raw_values[i + 1]))

    def __str__(self) -> str:
        return f"{self.desc} =\n{self.to_str()}"

    def to_str(self) -> str:
        """Get stringified property representation."""
        return "\n".join([f"    Region {i}: {region}" for i, region in enumerate(self.regions)])


class AvailablePeripheralsValue(PropertyValueBase):
    """Available Peripherals property."""

    __slots__ = ("value",)

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the AvailablePeripherals-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.value = raw_values[0]

    def to_int(self) -> int:
        """Get the raw integer portion of the property."""
        return self.value

    def to_str(self) -> str:
        """Get stringified property representation."""
        return ", ".join(
            [
                peripheral_tag.label
                for peripheral_tag in PeripheryTag
                if peripheral_tag.tag & self.value
            ]
        )


class AvailableCommandsValue(PropertyValueBase):
    """Available commands property."""

    __slots__ = ("value",)

    @property
    def tags(self) -> list[int]:
        """List of tags representing Available commands."""
        return [
            cmd_tag.tag
            for cmd_tag in CommandTag
            if cmd_tag.tag > 0 and (1 << cmd_tag.tag - 1) & self.value
        ]

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the AvailableCommands-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.value = raw_values[0]

    def __contains__(self, item: int) -> bool:
        return isinstance(item, int) and bool((1 << item - 1) & self.value)

    def to_str(self) -> str:
        """Get stringified property representation."""
        return [
            cmd_tag.label  # type: ignore
            for cmd_tag in CommandTag
            if cmd_tag.tag > 0 and (1 << cmd_tag.tag - 1) & self.value
        ]


class IrqNotifierPinValue(PropertyValueBase):
    """IRQ notifier pin property."""

    __slots__ = ("value",)

    @property
    def pin(self) -> int:
        """Number of the pin used for reporting IRQ."""
        return self.value & 0xFF

    @property
    def port(self) -> int:
        """Number of the port used for reporting IRQ."""
        return (self.value >> 8) & 0xFF

    @property
    def enabled(self) -> bool:
        """Indicates whether IRQ reporting is enabled."""
        return bool(self.value & (1 << 31))

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the IrqNotifierPin-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.value = raw_values[0]

    def __bool__(self) -> bool:
        return self.enabled

    def to_str(self) -> str:
        """Get stringified property representation."""
        return (
            f"IRQ Port[{self.port}], Pin[{self.pin}] is {'enabled' if self.enabled else 'disabled'}"
        )


class ExternalMemoryAttributesValue(PropertyValueBase):
    """Attributes for external memories."""

    __slots__ = (
        "value",
        "mem_id",
        "start_address",
        "total_size",
        "page_size",
        "sector_size",
        "block_size",
    )

    def __init__(self, tag: int, raw_values: list[int], mem_id: int = 0) -> None:
        """Initialize the ExternalMemoryAttributes-based property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        :param mem_id: ID of the external memory
        """
        super().__init__(tag)
        self.mem_id = mem_id
        self.start_address = (
            raw_values[1] if raw_values[0] & ExtMemPropTags.START_ADDRESS.tag else None
        )
        self.total_size = (
            raw_values[2] * 1024 if raw_values[0] & ExtMemPropTags.SIZE_IN_KBYTES.tag else None
        )
        self.page_size = raw_values[3] if raw_values[0] & ExtMemPropTags.PAGE_SIZE.tag else None
        self.sector_size = raw_values[4] if raw_values[0] & ExtMemPropTags.SECTOR_SIZE.tag else None
        self.block_size = raw_values[5] if raw_values[0] & ExtMemPropTags.BLOCK_SIZE.tag else None
        self.value = raw_values[0]

    def to_str(self) -> str:
        """Get stringified property representation."""
        str_values = []
        if self.start_address is not None:
            str_values.append(f"Start Address: 0x{self.start_address:08X}")
        if self.total_size is not None:
            str_values.append(f"Total Size:    {size_fmt(self.total_size)}")
        if self.page_size is not None:
            str_values.append(f"Page Size:     {size_fmt(self.page_size)}")
        if self.sector_size is not None:
            str_values.append(f"Sector Size:   {size_fmt(self.sector_size)}")
        if self.block_size is not None:
            str_values.append(f"Block Size:    {size_fmt(self.block_size)}")
        return ", ".join(str_values)


class FuseLock:
    """Fuse Lock."""

    def __init__(self, index: int, locked: bool) -> None:
        """Initialize object representing information about fuse lock.

        :param index: value of OTP index
        :param locked: status of the lock, true if locked
        """
        self.index = index
        self.locked = locked

    def __str__(self) -> str:
        status = "LOCKED" if self.locked else "UNLOCKED"
        return f"  FUSE{(self.index):03d}: {status}\r\n"


class FuseLockRegister:
    """Fuse Lock Register."""

    def __init__(self, value: int, index: int, start: int = 0) -> None:
        """Initialize object representing the OTP Controller Program Locked Status.

        :param value: value of the register
        :param index: index of the fuse
        :param start: shift to the start of the register

        """
        self.value = value
        self.index = index
        self.msg = ""
        self.bitfields: list[FuseLock] = []

        shift = 0
        for _ in range(start, 32):
            locked = (value >> shift) & 1
            self.bitfields.append(FuseLock(index + shift, bool(locked)))
            shift += 1

    def __str__(self) -> str:
        """Get stringified property representation."""
        if self.bitfields:
            for bitfield in self.bitfields:
                self.msg += str(bitfield)
        return f"\r\n{self.msg}"


class FuseLockedStatus(PropertyValueBase):
    """Class representing FuseLocked registers."""

    __slots__ = ("fuses",)

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the FuseLockedStatus property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.fuses: list[FuseLockRegister] = []
        idx = 0
        for count, val in enumerate(raw_values):
            start = 0
            if count == 0:
                start = 16
            self.fuses.append(FuseLockRegister(val, idx, start))
            idx += 32
            if count == 0:
                idx -= 16

    def to_str(self) -> str:
        """Get stringified property representation."""
        msg = "\r\n"
        for count, register in enumerate(self.fuses):
            msg += f"OTP Controller Program Locked Status {count} Register: {register}"
        return msg

    def get_fuses(self) -> list[FuseLock]:
        """Get list of fuses bitfield objects.

        :return: list of FuseLockBitfield objects
        """
        fuses = []
        for registers in self.fuses:
            fuses.extend(registers.bitfields)
        return fuses


class SHEFlashPartition(PropertyValueBase):
    """Class representing SHE Flash Partition property."""

    __slots__ = ("max_keys", "flash_size")

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the SHE Flash Partition property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.max_keys = raw_values[0] & 0x03
        self.flash_size = (raw_values[0] >> 8) & 0x03

    def to_str(self) -> str:
        """Get stringified property representation."""
        max_keys_mapping = {
            0: "0 Keys, CSEc disabled",
            1: "max 5 Key",
            2: "max 10 Keys",
            3: "max 20 Keys",
        }
        flash_size_mapping = {
            0: "64kB",
            1: "48kB",
            2: "32kB",
            3: "0kB",
        }
        return (
            f"{flash_size_mapping[self.flash_size]} EEPROM "
            f"with {max_keys_mapping[self.max_keys]}"
        )


class SHEBootMode(PropertyValueBase):
    """Class representing SHE Boot Mode property."""

    __slots__ = ("size", "mode")

    def __init__(self, tag: int, raw_values: list[int]) -> None:
        """Initialize the SHE Boot Mode property object.

        :param tag: Property tag, see: `PropertyTag`
        :param raw_values: List of integers representing the property
        """
        super().__init__(tag)
        self.size = raw_values[0] & 0x3FFF_FFFF
        self.mode = (raw_values[0] >> 30) & 0x03

    def to_str(self) -> str:
        """Get stringified property representation."""
        mode_mapping = {0: "Strict Boot", 1: "Serial Boot", 2: "Parallel Boot", 3: "Undefined"}
        return (
            f"SHE Boot Mode: {mode_mapping.get(self.mode, 'Unknown')} ({self.mode})\n"
            f"SHE Boot Size: {size_fmt(self.size // 8)} (0x{self.size:_x})"
        )

    def __str__(self) -> str:
        return self.to_str()


########################################################################################################################
# McuBoot property response parser
########################################################################################################################

PROPERTIES: dict[int, dict] = {
    PropertyTag.CURRENT_VERSION.tag: {"class": VersionValue, "kwargs": {}},
    PropertyTag.AVAILABLE_PERIPHERALS.tag: {
        "class": AvailablePeripheralsValue,
        "kwargs": {},
    },
    PropertyTag.FLASH_START_ADDRESS.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "hex"},
    },
    PropertyTag.FLASH_SIZE.tag: {"class": IntValue, "kwargs": {"str_format": "size"}},
    PropertyTag.FLASH_SECTOR_SIZE.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "size"},
    },
    PropertyTag.FLASH_BLOCK_COUNT.tag: {"class": IntValue, "kwargs": {"str_format": "dec"}},
    PropertyTag.AVAILABLE_COMMANDS.tag: {"class": AvailableCommandsValue, "kwargs": {}},
    PropertyTag.CRC_CHECK_STATUS.tag: {
        "class": EnumValue,
        "kwargs": {"enum": StatusCode, "na_msg": "Unknown CRC Status code"},
    },
    PropertyTag.VERIFY_WRITES.tag: {
        "class": BoolValue,
        "kwargs": {"true_string": "ON", "false_string": "OFF"},
    },
    PropertyTag.LAST_ERROR.tag: {
        "class": EnumValue,
        "kwargs": {"enum": StatusCode, "na_msg": "Unknown Error"},
    },
    PropertyTag.MAX_PACKET_SIZE.tag: {"class": IntValue, "kwargs": {"str_format": "size"}},
    PropertyTag.RESERVED_REGIONS.tag: {"class": ReservedRegionsValue, "kwargs": {}},
    PropertyTag.VALIDATE_REGIONS.tag: {
        "class": BoolValue,
        "kwargs": {"true_string": "ON", "false_string": "OFF"},
    },
    PropertyTag.RAM_START_ADDRESS.tag: {"class": IntValue, "kwargs": {"str_format": "hex"}},
    PropertyTag.RAM_SIZE.tag: {"class": IntValue, "kwargs": {"str_format": "size"}},
    PropertyTag.SYSTEM_DEVICE_IDENT.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "hex"},
    },
    PropertyTag.FLASH_SECURITY_STATE.tag: {
        "class": BoolValue,
        "kwargs": {
            "true_values": (0x00000000, 0x5AA55AA5),
            "true_string": "UNSECURE",
            "false_values": (0x00000001, 0xC33CC33C),
            "false_string": "SECURE",
        },
    },
    PropertyTag.UNIQUE_DEVICE_IDENT.tag: {"class": DeviceUidValue, "kwargs": {}},
    PropertyTag.FLASH_FAC_SUPPORT.tag: {
        "class": BoolValue,
        "kwargs": {"true_string": "ON", "false_string": "OFF"},
    },
    PropertyTag.FLASH_ACCESS_SEGMENT_SIZE.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "size"},
    },
    PropertyTag.FLASH_ACCESS_SEGMENT_COUNT.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "int32"},
    },
    PropertyTag.FLASH_READ_MARGIN.tag: {
        "class": EnumValue,
        "kwargs": {"enum": FlashReadMargin, "na_msg": "Unknown Margin"},
    },
    PropertyTag.QSPI_INIT_STATUS.tag: {
        "class": EnumValue,
        "kwargs": {"enum": StatusCode, "na_msg": "Unknown Error"},
    },
    PropertyTag.TARGET_VERSION.tag: {"class": VersionValue, "kwargs": {}},
    PropertyTag.EXTERNAL_MEMORY_ATTRIBUTES.tag: {
        "class": ExternalMemoryAttributesValue,
        "kwargs": {"mem_id": None},
    },
    PropertyTag.RELIABLE_UPDATE_STATUS.tag: {
        "class": EnumValue,
        "kwargs": {"enum": StatusCode, "na_msg": "Unknown Error"},
    },
    PropertyTag.FLASH_PAGE_SIZE.tag: {"class": IntValue, "kwargs": {"str_format": "size"}},
    PropertyTag.IRQ_NOTIFIER_PIN.tag: {"class": IrqNotifierPinValue, "kwargs": {}},
    PropertyTag.PFR_KEYSTORE_UPDATE_OPT.tag: {
        "class": EnumValue,
        "kwargs": {"enum": PfrKeystoreUpdateOpt, "na_msg": "Unknown"},
    },
    PropertyTag.BYTE_WRITE_TIMEOUT_MS.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "dec"},
    },
    PropertyTag.FUSE_LOCKED_STATUS.tag: {
        "class": FuseLockedStatus,
        "kwargs": {},
    },
    PropertyTag.BOOT_STATUS_REGISTER.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "int32"},
    },
    PropertyTag.FIRMWARE_VERSION.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "int32"},
    },
    PropertyTag.FUSE_PROGRAM_VOLTAGE.tag: {
        "class": BoolValue,
        "kwargs": {
            "true_string": "Over Drive Voltage (2.5 V)",
            "false_string": "Normal Voltage (1.8 V)",
        },
    },
    PropertyTag.SHE_FLASH_PARTITION.tag: {"class": SHEFlashPartition, "kwargs": {}},
    PropertyTag.SHE_BOOT_MODE.tag: {"class": SHEBootMode, "kwargs": {}},
    PropertyTag.UNKNOWN.tag: {
        "class": IntListValue,
        "kwargs": {"str_format": "hex"},
    },
}

PROPERTIES_KW45XX = {
    PropertyTagKw45xx.VERIFY_ERASE.tag: {
        "class": BoolValue,
        "kwargs": {"true_string": "ENABLE", "false_string": "DISABLE"},
    },
    PropertyTagKw45xx.BOOT_STATUS_REGISTER.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "hex"},
    },
    PropertyTagKw45xx.FIRMWARE_VERSION.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "int32"},
    },
    PropertyTagKw45xx.FUSE_PROGRAM_VOLTAGE.tag: {
        "class": BoolValue,
        "kwargs": {
            "true_string": "Over Drive Voltage (2.5 V)",
            "false_string": "Normal Voltage (1.8 V)",
        },
    },
}

PROPERTIES_KW47XX = {
    PropertyTagKw47xx.VERIFY_ERASE.tag: {
        "class": BoolValue,
        "kwargs": {"true_string": "ENABLE", "false_string": "DISABLE"},
    },
    PropertyTagKw47xx.BOOT_STATUS_REGISTER.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "hex"},
    },
    PropertyTagKw47xx.FIRMWARE_VERSION.tag: {
        "class": IntValue,
        "kwargs": {"str_format": "int32"},
    },
    PropertyTagKw47xx.FUSE_PROGRAM_VOLTAGE.tag: {
        "class": BoolValue,
        "kwargs": {
            "true_string": "Over Drive Voltage (2.5 V)",
            "false_string": "Normal Voltage (1.8 V)",
        },
    },
}


PROPERTIES_MCXA1XX = {
    PropertyTagMcxa1xx.LIFE_CYCLE_STATE.tag: {
        "class": BoolValue,
        "kwargs": {
            "true_values": (0x00000000, 0x5AA55AA5),
            "true_string": "development life cycle",
            "false_values": (0x00000001, 0xC33CC33C),
            "false_string": "deployment life cycle",
        },
    },
}

PROPERTIES_OVERRIDE = {
    "kw47_series": PROPERTIES_KW47XX,
    "kw45_series": PROPERTIES_KW45XX,
    "mcxa1_series": PROPERTIES_MCXA1XX,
}
PROPERTY_TAG_OVERRIDE = {
    "kw47_series": PropertyTagKw47xx,
    "kw45_series": PropertyTagKw45xx,
    "mcxa1_series": PropertyTagMcxa1xx,
}


def parse_property_value(
    property_tag: Union[int, PropertyTag],
    raw_values: list[int],
    ext_mem_id: Optional[int] = None,
    family: Optional[FamilyRevision] = None,
) -> Optional[PropertyValueBase]:
    """Parse the property value received from the device.

    :param property_tag: Tag representing the property
    :param raw_values: Data received from the device
    :param ext_mem_id: ID of the external memory used to read the property, defaults to None
    :param family: supported family
    :return: Object representing the property
    """
    if isinstance(property_tag, PropertyTag):
        property_tag = property_tag.tag
    assert isinstance(property_tag, int)
    assert isinstance(raw_values, list)
    properties_dict = deepcopy(PROPERTIES)
    overridden_series = None
    if family:
        db = get_db(family)
        overridden_series = db.get_str(DatabaseManager().BLHOST, "overridden_properties", "")
    if overridden_series:
        properties_dict.update(PROPERTIES_OVERRIDE[overridden_series])
    if property_tag not in list(properties_dict.keys()):
        property_tag = PropertyTag.UNKNOWN.tag
    property_value = next(value for key, value in properties_dict.items() if key == property_tag)
    cls: Callable = property_value["class"]
    kwargs: dict = property_value["kwargs"]
    if "mem_id" in kwargs:
        kwargs["mem_id"] = ext_mem_id
    obj = cls(property_tag, raw_values, **kwargs)
    if overridden_series:
        property_tag_override = PROPERTY_TAG_OVERRIDE[overridden_series].from_tag(property_tag)
        obj.name = property_tag_override.label
        obj.desc = property_tag_override.description
    return obj


def get_property_tag_label(mboot_property: Union[PropertyTag, int]) -> tuple[int, str]:
    """Get property tag and label."""
    if isinstance(mboot_property, int):
        try:
            prop = PropertyTag.from_tag(mboot_property)
            return prop.tag, prop.label
        except SPSDKKeyError:
            logger.warning(f"Unknown property id: {mboot_property} ({hex(mboot_property)})")
            return mboot_property, "Unknown"
    return mboot_property.tag, mboot_property.label
