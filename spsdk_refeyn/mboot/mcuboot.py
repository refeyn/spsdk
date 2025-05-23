#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2016-2018 Martin Olejar
# Copyright 2019-2024 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

"""Module for communication with the bootloader."""

import logging
import time
from types import TracebackType
from typing import Callable, Optional, Type, Union

from spsdk_refeyn.mboot.commands import (
    CmdPacket,
    CmdResponse,
    CommandFlag,
    CommandTag,
    GenericResponse,
    GetPropertyResponse,
    NoResponse,
    ReadMemoryResponse,
)
from spsdk_refeyn.mboot.error_codes import StatusCode, stringify_status_code
from spsdk_refeyn.mboot.exceptions import (
    McuBootCommandError,
    McuBootConnectionError,
    McuBootDataAbortError,
    McuBootError,
    SPSDKError,
)
from spsdk_refeyn.mboot.properties import (
    AvailableCommandsValue,
    PropertyTag,
    PropertyValueBase,
    get_property_tag_label,
    parse_property_value,
)
from spsdk_refeyn.mboot.protocol.base import MbootProtocolBase
from spsdk_refeyn.utils.interfaces.device.usb_device import UsbDevice

logger = logging.getLogger(__name__)


########################################################################################################################
# McuBoot Class
########################################################################################################################
class McuBoot:  # pylint: disable=too-many-public-methods
    """Class for communication with the bootloader."""

    DEFAULT_MAX_PACKET_SIZE = 32

    @property
    def status_code(self) -> int:
        """Return status code of the last operation."""
        return self._status_code

    @property
    def status_string(self) -> str:
        """Return status string."""
        return stringify_status_code(self._status_code)

    @property
    def is_opened(self) -> bool:
        """Return True if the device is open."""
        return self._interface.is_opened

    def __init__(
        self, interface: MbootProtocolBase, cmd_exception: bool = False
    ) -> None:
        """Initialize the McuBoot object.

        :param interface: The instance of communication interface class
        :param cmd_exception: True to throw McuBootCommandError on any error;
                False to set status code only
                Note: some operation might raise McuBootCommandError is all cases

        """
        self._cmd_exception = cmd_exception
        self._status_code = StatusCode.SUCCESS.tag
        self._interface = interface
        self.reopen = False
        self.enable_data_abort = False
        self._pause_point: Optional[int] = None
        self.available_commands_lst: list[CommandTag] = []
        self.max_packet_size: Optional[int] = None

    def __enter__(self) -> "McuBoot":
        self.reopen = True
        self.open()
        return self

    def __exit__(
        self,
        exception_type: Optional[Type[Exception]] = None,
        exception_value: Optional[Exception] = None,
        traceback: Optional[TracebackType] = None,
    ) -> None:
        self.close()

    def _process_cmd(self, cmd_packet: CmdPacket) -> CmdResponse:
        """Process Command.

        :param cmd_packet: Command Packet
        :return: command response derived from the CmdResponse
        :raises McuBootConnectionError: Timeout Error
        :raises McuBootCommandError: Error during command execution on the target
        """
        if not self.is_opened:
            logger.info("TX: Device not opened")
            raise McuBootConnectionError("Device not opened")

        logger.debug(f"TX-PACKET: {str(cmd_packet)}")

        try:
            self._interface.write_command(cmd_packet)
            response = self._interface.read()
        except TimeoutError:
            self._status_code = StatusCode.NO_RESPONSE.tag
            logger.debug("RX-PACKET: No Response, Timeout Error !")
            response = NoResponse(cmd_tag=cmd_packet.header.tag)

        assert isinstance(response, CmdResponse)
        logger.debug(f"RX-PACKET: {str(response)}")
        self._status_code = response.status

        if self._cmd_exception and self._status_code != StatusCode.SUCCESS:
            raise McuBootCommandError(
                CommandTag.get_label(cmd_packet.header.tag), response.status
            )
        logger.info(f"CMD: Status: {self.status_string}")
        return response

    def _read_data(
        self,
        cmd_tag: CommandTag,
        length: int,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bytes:
        """Read data from device.

        :param cmd_tag: Tag indicating the read command.
        :param length: Length of data to read
        :param progress_callback: Callback for updating the caller about the progress
        :raises McuBootConnectionError: Timeout error or a problem opening the interface
        :raises McuBootCommandError: Error during command execution on the target
        :return: Data read from the device
        """
        data = b""

        if not self.is_opened:
            logger.error("RX: Device not opened")
            raise McuBootConnectionError("Device not opened")
        while True:
            try:
                response = self._interface.read()
            except McuBootDataAbortError as e:
                logger.error(f"RX: {e}")
                logger.info("Try increasing the timeout value")
                response = self._interface.read()
            except TimeoutError:
                self._status_code = StatusCode.NO_RESPONSE.tag
                logger.error("RX: No Response, Timeout Error !")
                response = NoResponse(cmd_tag=cmd_tag.tag)
                break

            if isinstance(response, bytes):
                data += response
                if progress_callback:
                    progress_callback(len(data), length)

            elif isinstance(response, GenericResponse):
                logger.debug(f"RX-PACKET: {str(response)}")
                self._status_code = response.status
                if response.cmd_tag == cmd_tag:
                    break

        if len(data) < length or self.status_code != StatusCode.SUCCESS:
            status_info = (
                StatusCode.get_label(self._status_code)
                if self._status_code in StatusCode.tags()
                else f"0x{self._status_code:08X}"
            )
            logger.debug(
                f"CMD: Received {len(data)} from {length} Bytes, {status_info}"
            )
            if self._cmd_exception:
                assert isinstance(response, CmdResponse)
                raise McuBootCommandError(cmd_tag.label, response.status)
        else:
            logger.info(f"CMD: Successfully Received {len(data)} from {length} Bytes")

        return data[:length] if len(data) > length else data

    def _send_data(
        self,
        cmd_tag: CommandTag,
        data: list[bytes],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Send Data part of specific command.

        :param cmd_tag: Tag indicating the command
        :param data: List of data chunks to send
        :param progress_callback: Callback for updating the caller about the progress
        :raises McuBootConnectionError: Timeout error
        :raises McuBootCommandError: Error during command execution on the target
        :return: True if the operation is successful
        """
        if not self.is_opened:
            logger.info("TX: Device Disconnected")
            raise McuBootConnectionError("Device Disconnected !")

        total_sent = 0
        total_to_send = sum(len(chunk) for chunk in data)
        # this difference is applicable for load-image and program-aeskey commands
        expect_response = cmd_tag != CommandTag.NO_COMMAND
        self._interface.allow_abort = self.enable_data_abort
        try:
            for data_chunk in data:
                self._interface.write_data(data_chunk)
                total_sent += len(data_chunk)
                if progress_callback:
                    progress_callback(total_sent, total_to_send)
                if self._pause_point and total_sent > self._pause_point:
                    time.sleep(0.1)
                    self._pause_point = None

            if expect_response:
                response = self._interface.read()
        except TimeoutError as e:
            self._status_code = StatusCode.NO_RESPONSE.tag
            logger.error("RX: No Response, Timeout Error !")
            raise McuBootConnectionError("No Response from Device") from e
        except SPSDKError as e:
            logger.error(f"RX: {e}")
            if expect_response:
                response = self._interface.read()
            else:
                self._status_code = StatusCode.SENDING_OPERATION_CONDITION_ERROR.tag

        if expect_response:
            assert isinstance(response, CmdResponse)
            logger.debug(f"RX-PACKET: {str(response)}")
            self._status_code = response.status
            if response.status != StatusCode.SUCCESS:
                status_info = (
                    StatusCode.get_label(self._status_code)
                    if self._status_code in StatusCode.tags()
                    else f"0x{self._status_code:08X}"
                )
                logger.debug(f"CMD: Send Error, {status_info}")
                if self._cmd_exception:
                    raise McuBootCommandError(cmd_tag.label, response.status)
                return False

        logger.info(f"CMD: Successfully Send {total_sent} out of {total_to_send} Bytes")
        return total_sent == total_to_send

    def _get_max_packet_size(self) -> int:
        """Get max packet size.

        :return int: max packet size in B
        """
        if self.max_packet_size is not None:
            logger.debug(f"Using cached max_packet_size={self.max_packet_size}")
            return self.max_packet_size

        packet_size_property = None
        try:
            packet_size_property = self.get_property(
                prop_tag=PropertyTag.MAX_PACKET_SIZE
            )
        except McuBootError:
            pass
        if packet_size_property is None:
            packet_size_property = [self.DEFAULT_MAX_PACKET_SIZE]
            logger.warning(
                f"CMD: Unable to get MAX PACKET SIZE, using: {self.DEFAULT_MAX_PACKET_SIZE}"
            )
        self.max_packet_size = packet_size_property[0]
        logger.info(f"CMD: Max Packet Size = {self.max_packet_size}")
        return self.max_packet_size

    def _split_data(self, data: bytes) -> list[bytes]:
        """Split data to send if necessary.

        :param data: Data to send
        :return: List of data splices
        """
        if not self._interface.need_data_split:
            return [data]
        max_packet_size = self._get_max_packet_size()
        return [
            data[i : i + max_packet_size] for i in range(0, len(data), max_packet_size)
        ]

    def open(self) -> None:
        """Connect to the device."""
        logger.info(f"Connect: {str(self._interface)}")
        self._interface.open()

    def close(self) -> None:
        """Disconnect from the device."""
        logger.info(f"Closing: {str(self._interface)}")
        self._interface.close()

    def get_property_list(self) -> list[PropertyValueBase]:
        """Get a list of available properties.

        :return: List of available properties.
        :raises McuBootCommandError: Failure to read properties list
        :raises McuBootError: Property values cannot be parsed
        """
        property_list: list[PropertyValueBase] = []
        for property_tag in PropertyTag:
            try:
                values = self.get_property(property_tag)
            except McuBootCommandError:
                continue

            if values:
                prop = parse_property_value(property_tag.tag, values)
                if prop is None:
                    raise McuBootError("Property values cannot be parsed")
                property_list.append(prop)

        self._status_code = StatusCode.SUCCESS.tag
        if not property_list:
            self._status_code = StatusCode.FAIL.tag
            if self._cmd_exception:
                raise McuBootCommandError("GetPropertyList", self.status_code)

        return property_list

    @property
    def available_commands(self) -> list[CommandTag]:
        """Get a list of supported commands.

        :return: List of supported commands
        """
        if self.available_commands_lst:
            return self.available_commands_lst

        values = None
        props = None

        try:
            values = self.get_property(PropertyTag.AVAILABLE_COMMANDS)
        except McuBootCommandError:
            pass

        if values:
            props = parse_property_value(PropertyTag.AVAILABLE_COMMANDS.tag, values)

        if isinstance(props, AvailableCommandsValue):
            self.available_commands_lst = [
                CommandTag.from_tag(tag) for tag in props.tags
            ]

        return self.available_commands_lst

    def flash_erase_all(self, mem_id: int = 0) -> bool:
        """Erase complete flash memory without recovering flash security section.

        :param mem_id: Memory ID
        :return: False in case of any problem; True otherwise
        """
        logger.info(f"CMD: FlashEraseAll(mem_id={mem_id})")
        cmd_packet = CmdPacket(CommandTag.FLASH_ERASE_ALL, CommandFlag.NONE.tag, mem_id)
        response = self._process_cmd(cmd_packet)
        return response.status == StatusCode.SUCCESS

    def read_memory(
        self,
        address: int,
        length: int,
        mem_id: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        fast_mode: bool = False,
    ) -> Optional[bytes]:
        """Read data from MCU memory.

        :param address: Start address
        :param length: Count of bytes
        :param mem_id: Memory ID
        :param fast_mode: Fast mode for USB-HID data transfer, not reliable !!!
        :param progress_callback: Callback for updating the caller about the progress
        :return: Data read from the memory; None in case of a failure
        """
        logger.info(
            f"CMD: ReadMemory(address=0x{address:08X}, length={length}, mem_id={mem_id})"
        )
        mem_id = _clamp_down_memory_id(memory_id=mem_id)

        # workaround for better USB-HID reliability
        if isinstance(self._interface.device, UsbDevice) and not fast_mode:
            payload_size = self._get_max_packet_size()
            packets = length // payload_size
            remainder = length % payload_size
            if remainder:
                packets += 1

            data = b""

            for idx in range(packets):
                if idx == packets - 1 and remainder:
                    data_len = remainder
                else:
                    data_len = payload_size

                cmd_packet = CmdPacket(
                    CommandTag.READ_MEMORY,
                    CommandFlag.NONE.tag,
                    address + idx * payload_size,
                    data_len,
                    mem_id,
                )
                cmd_response = self._process_cmd(cmd_packet)
                if cmd_response.status == StatusCode.SUCCESS:
                    data += self._read_data(CommandTag.READ_MEMORY, data_len)
                    if progress_callback:
                        progress_callback(len(data), length)
                    if self._status_code == StatusCode.NO_RESPONSE:
                        logger.warning(
                            f"CMD: NO RESPONSE, received {len(data)}/{length} B"
                        )
                        return data
                else:
                    return b""

            return data

        cmd_packet = CmdPacket(
            CommandTag.READ_MEMORY, CommandFlag.NONE.tag, address, length, mem_id
        )
        cmd_response = self._process_cmd(cmd_packet)
        if cmd_response.status == StatusCode.SUCCESS:
            assert isinstance(cmd_response, ReadMemoryResponse)
            return self._read_data(
                CommandTag.READ_MEMORY, cmd_response.length, progress_callback
            )
        return None

    def write_memory(
        self,
        address: int,
        data: bytes,
        mem_id: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Write data into MCU memory.

        :param address: Start address
        :param data: List of bytes
        :param progress_callback: Callback for updating the caller about the progress
        :param mem_id: Memory ID, see ExtMemId; additionally use `0` for internal memory
        :return: False in case of any problem; True otherwise
        """
        logger.info(
            f"CMD: WriteMemory(address=0x{address:08X}, length={len(data)}, mem_id={mem_id})"
        )
        data_chunks = self._split_data(data=data)
        mem_id = _clamp_down_memory_id(memory_id=mem_id)
        cmd_packet = CmdPacket(
            CommandTag.WRITE_MEMORY,
            CommandFlag.HAS_DATA_PHASE.tag,
            address,
            len(data),
            mem_id,
        )
        if self._process_cmd(cmd_packet).status == StatusCode.SUCCESS:
            return self._send_data(
                CommandTag.WRITE_MEMORY, data_chunks, progress_callback
            )
        return False

    def fill_memory(self, address: int, length: int, pattern: int = 0xFFFFFFFF) -> bool:
        """Fill MCU memory with specified pattern.

        :param address: Start address (must be word aligned)
        :param length: Count of words (must be word aligned)
        :param pattern: Count of wrote bytes
        :return: False in case of any problem; True otherwise
        """
        logger.info(
            f"CMD: FillMemory(address=0x{address:08X}, length={length}, pattern=0x{pattern:08X})"
        )
        cmd_packet = CmdPacket(
            CommandTag.FILL_MEMORY, CommandFlag.NONE.tag, address, length, pattern
        )
        return self._process_cmd(cmd_packet).status == StatusCode.SUCCESS

    def get_property(
        self, prop_tag: Union[PropertyTag, int], index: int = 0
    ) -> Optional[list[int]]:
        """Get specified property value.

        :param prop_tag: Property TAG (see Properties Enum)
        :param index: External memory ID or internal memory region index (depends on property type)
        :return: list integers representing the property; None in case no response from device
        :raises McuBootError: If received invalid get-property response
        """
        property_id, label = get_property_tag_label(prop_tag)
        logger.info(f"CMD: GetProperty({label}, index={index!r})")
        cmd_packet = CmdPacket(
            CommandTag.GET_PROPERTY, CommandFlag.NONE.tag, property_id, index
        )
        cmd_response = self._process_cmd(cmd_packet)
        if cmd_response.status == StatusCode.SUCCESS:
            if isinstance(cmd_response, GetPropertyResponse):
                return cmd_response.values
            raise McuBootError(
                f"Received invalid get-property response: {str(cmd_response)}"
            )
        return None

    def configure_memory(self, address: int, mem_id: int) -> bool:
        """Configure memory.

        :param address: The address in memory where are locating configuration data
        :param mem_id: Memory ID
        :return: False in case of any problem; True otherwise
        """
        logger.info(f"CMD: ConfigureMemory({mem_id}, address=0x{address:08X})")
        cmd_packet = CmdPacket(
            CommandTag.CONFIGURE_MEMORY, CommandFlag.NONE.tag, mem_id, address
        )
        return self._process_cmd(cmd_packet).status == StatusCode.SUCCESS


####################
# Helper functions #
####################


def _clamp_down_memory_id(memory_id: int) -> int:
    if memory_id > 255 or memory_id == 0:
        return memory_id
    logger.warning(
        "Note: memoryId is not required when accessing mapped external memory"
    )
    return 0
