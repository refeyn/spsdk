#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright 2020-2025 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

"""Miscellaneous functions used throughout the SPSDK."""

import logging

from spsdk_refeyn.utils.database import DatabaseManager, Features

logger = logging.getLogger(__name__)


class FamilyRevision:
    """Class keeping family name and revision information."""

    def __init__(self, name: str, revision: str = "latest") -> None:
        """Family revision class constructor.

        :param family: Mandatory family
        :param revision: Optionally revision, defaults to "latest"
        """
        self.name = DatabaseManager().quick_info.devices.get_correct_name(name)
        if name != self.name:
            logger.debug(
                f"The abbreviation family name '{name}' "
                f"has been translated to current one: '{self.name}')"
            )

        self.revision = revision

    def __str__(self) -> str:
        return f"{self.name}, Revision: {self.revision}"

    def __repr__(self) -> str:
        return f"{self.name}, Revision: {self.revision}"

    def get_real_revision(self) -> str:
        """Returns real name of revision (translate possible latest to real name)."""
        if self.revision != "latest":
            return self.revision

        return DatabaseManager().quick_info.devices.devices[self.name].latest_rev

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FamilyRevision):
            return self.name == other.name and self.get_real_revision() == other.get_real_revision()
        return False

    def __hash__(self) -> int:
        return hash((self.name, self.revision))

    def __lt__(self, other: "FamilyRevision") -> bool:
        if isinstance(other, FamilyRevision):
            return self.name < other.name
        return NotImplemented

    def casefold(self) -> "FamilyRevision":
        """Case Fold of device and revision names."""
        return FamilyRevision(self.name.casefold(), self.revision.casefold())


def get_db(family: FamilyRevision) -> Features:
    """Get family feature database for specified family revision.

    :param family: The family revision object to get features for.
    :return: Features object containing all feature data for the family.
    """
    return DatabaseManager().db.get_device_features(family.name, family.revision)
