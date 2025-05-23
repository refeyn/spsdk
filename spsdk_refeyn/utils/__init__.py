#!/usr/bin/env python
# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------

"""Module containing various functions/modules used throughout the SPSDK."""

from spsdk_refeyn.utils.exceptions import (
    SPSDKRegsError,
    SPSDKRegsErrorBitfieldNotFound,
    SPSDKRegsErrorEnumNotFound,
    SPSDKRegsErrorRegisterGroupMishmash,
    SPSDKRegsErrorRegisterNotFound,
)

__all__ = [
    "SPSDKRegsError",
    "SPSDKRegsErrorBitfieldNotFound",
    "SPSDKRegsErrorEnumNotFound",
    "SPSDKRegsErrorRegisterGroupMishmash",
    "SPSDKRegsErrorRegisterNotFound",
]
