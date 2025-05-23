#!/usr/bin/env python
# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------

"""Module provides exceptions for SPSDK utilities."""

from spsdk.exceptions import SPSDKError


class SPSDKRegsError(SPSDKError):
    """General Error group for utilities SPSDK registers module."""


class SPSDKRegsErrorRegisterGroupMishmash(SPSDKRegsError):
    """Register Group inconsistency problem."""


class SPSDKRegsErrorRegisterNotFound(SPSDKRegsError):
    """Register has not been found."""


class SPSDKRegsErrorBitfieldNotFound(SPSDKRegsError):
    """Bitfield has not been found."""


class SPSDKRegsErrorEnumNotFound(SPSDKRegsError):
    """Enum has not been found."""


class SPSDKTimeoutError(SPSDKError, TimeoutError):
    """SPSDK Timeout."""
