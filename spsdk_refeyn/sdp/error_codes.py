#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2017-2018 Martin Olejar
# Copyright 2019-2024 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

"""Error codes defined by the SDP protocol."""

from spsdk_refeyn.utils.spsdk_enum import SpsdkEnum


########################################################################################################################
# SDP Status Codes (Errors)
########################################################################################################################
class StatusCode(SpsdkEnum):
    """SDP status codes."""

    SUCCESS = (0, "Success", "Success")
    CMD_FAILURE = (1, "CommandFailure", "Command Failure")
    HAB_IS_LOCKED = (2, "HabIsLocked", "HAB Is Locked")
    READ_DATA_FAILURE = (10, "ReadDataFailure", "Read Register/Data Failure")
    WRITE_REGISTER_FAILURE = (11, "WriteRegisterFailure", "Write Register Failure")
    WRITE_IMAGE_FAILURE = (12, "WriteImageFailure", "Write Image Failure")
    WRITE_DCD_FAILURE = (13, "WriteDcdFailure", "Write DCD Failure")
    WRITE_CSF_FAILURE = (14, "WriteCsfFailure", "Write CSF Failure")
    SKIP_DCD_HEADER_FAILURE = (15, "SkipDcdHeaderFailure", "Skip DCD Header Failure")


########################################################################################################################
# HAB Status Codes (Errors)
########################################################################################################################
