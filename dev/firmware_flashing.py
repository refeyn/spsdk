# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------
import logging
import time
from pathlib import Path
from typing import Callable, Optional, Sequence

from spsdk_refeyn.exceptions import SPSDKError
from spsdk_refeyn.mboot import MbootDeviceTypes
from spsdk_refeyn.mboot.interfaces.uart import MbootUARTInterface
from spsdk_refeyn.mboot.interfaces.usb import MbootUSBInterface
from spsdk_refeyn.mboot.mcuboot import McuBoot
from spsdk_refeyn.sdp.interfaces.uart import SdpUARTInterface
from spsdk_refeyn.sdp.interfaces.usb import SdpUSBInterface
from spsdk_refeyn.sdp.sdp import SDP, SDPDeviceTypes

IVT_FLASHLOADER = Path(r"ivt_flashloader.bin")
IVT_LOCATION = 0x20208200

USE_UART = False


def read_status(device_id: Optional[str] = None) -> Optional[int]:
    interfaces: Sequence[SDPDeviceTypes]
    if USE_UART:
        interfaces = SdpUARTInterface.scan(port=device_id)
    else:
        interfaces = SdpUSBInterface.scan(device_id=device_id)
    if interfaces:
        with SDP(interfaces[0]) as sdp:
            return sdp.read_status()
    return None


def flash_bootloader(device_id: Optional[str], filePath: Path, location: int) -> None:
    interfaces: Sequence[SDPDeviceTypes]
    if USE_UART:
        interfaces = SdpUARTInterface.scan(port=device_id)
    else:
        interfaces = SdpUSBInterface.scan(device_id=device_id)
    if interfaces:
        with SDP(interfaces[0]) as sdp, filePath.open("rb") as f:
            fileContent = f.read()
            sdp.write_file(location, fileContent)
            sdp.jump_and_run(location)


def read_mem(
    address: int,
    length: int,
    mem_id: int = 0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    fast_mode: bool = False,
) -> Optional[bytes]:
    interfaces: Sequence[MbootDeviceTypes]
    if USE_UART:
        interfaces = MbootUARTInterface.scan("0x15a2:0x0073", timeout=5242000)
    else:
        interfaces = MbootUSBInterface.scan("0x15a2:0x0073", timeout=5242000)
    if not interfaces:
        raise SPSDKError("No USB interfaces found")
    interface = interfaces[0]
    with McuBoot(interface) as mb:
        return mb.read_memory(address, length, mem_id, progress_callback, fast_mode)


def read_from_bl(device_id: str) -> None:
    interfaces: Sequence[MbootDeviceTypes]
    if USE_UART:
        interfaces = MbootUARTInterface.scan("0x15a2:0x0073", timeout=5242000)
    else:
        interfaces = MbootUSBInterface.scan("0x15a2:0x0073", timeout=5242000)
    if not interfaces:
        raise SPSDKError("No USB interfaces found")
    interface = interfaces[0]

    with McuBoot(interface) as mb:
        property_list = mb.get_property_list()
        prop1 = mb.get_property(1, 0)
        prop2 = mb.get_property(24, 0)
        mb.fill_memory(0x20202000, 4, 0xC0000007)
        mb.fill_memory(0x20202004, 4, 0)
        mb.configure_memory(0x20202000, 9)

    for prop in property_list:
        print(prop)

    print(prop1)
    print(prop2)


def flash_fw(file: Path) -> None:
    interfaces: Sequence[MbootDeviceTypes]
    if USE_UART:
        interfaces = MbootUARTInterface.scan("0x15a2:0x0073", timeout=5242000)
    else:
        interfaces = MbootUSBInterface.scan("0x15a2:0x0073", timeout=5242000)
    if not interfaces:
        raise SPSDKError("No USB interfaces found")
    interface = interfaces[0]
    with McuBoot(interface) as mb:
        mb.flash_erase_all(9)
        with file.open("rb") as f:
            mb.write_memory(0x60000000, f.read())


logger = logging.getLogger()
logging.basicConfig(level=logging.WARNING)

flash_bootloader("0x1fc9:0x0130", IVT_FLASHLOADER, IVT_LOCATION)
time.sleep(10.0)
read_from_bl("0x15a2:0x0073")

readReg = read_mem(0x400AC040, 4, mem_id=0)
print(readReg)
print("Reading 12 bytes from 0x6001e90c")
print(read_mem(0x6001E90C, 12))
flash_fw(Path(r"dev\NXP_2.bin"))
print("Reading 12 bytes from 0x6001e90c")
print(read_mem(0x6001E90C, 12))
