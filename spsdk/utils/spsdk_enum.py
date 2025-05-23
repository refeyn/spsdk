#!/usr/bin/env python
# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------

"""Custom enum extension."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from typing_extensions import Self

from spsdk.exceptions import SPSDKKeyError


@dataclass(frozen=True)
class SpsdkEnumMember:
    """SPSDK Enum member."""

    tag: int
    label: str
    description: Optional[str] = None


class SpsdkEnum(SpsdkEnumMember, Enum):
    """SPSDK Enum type."""

    def __eq__(self, __value: object) -> bool:
        return self.tag == __value or self.label == __value

    def __hash__(self) -> int:
        return hash((self.tag, self.label, self.description))

    @classmethod
    def tags(cls) -> list[int]:
        """Get list of tags of all enum members.

        :return: List of all tags
        """
        return [value.tag for value in cls.__members__.values()]

    @classmethod
    def get_label(cls, tag: int) -> str:
        """Get label of enum member with given tag.

        :param tag: Tag to be used for searching
        :return: Label of found enum member
        """
        value = cls.from_tag(tag)
        return value.label

    @classmethod
    def get_description(cls, tag: int, default: Optional[str] = None) -> Optional[str]:
        """Get description of enum member with given tag.

        :param tag: Tag to be used for searching
        :param default: Default value if member contains no description
        :return: Description of found enum member
        """
        value = cls.from_tag(tag)
        return value.description or default

    @classmethod
    def from_tag(cls, tag: int) -> Self:
        """Get enum member with given tag.

        :param tag: Tag to be used for searching
        :raises SPSDKKeyError: If enum with given label is not found
        :return: Found enum member
        """
        for item in cls.__members__.values():
            if item.tag == tag:
                return item
        raise SPSDKKeyError(
            f"There is no {cls.__name__} item in with tag {tag} defined"
        )

    @classmethod
    def from_label(cls, label: str) -> Self:
        """Get enum member with given label.

        :param label: Label to be used for searching
        :raises SPSDKKeyError: If enum with given label is not found
        :return: Found enum member
        """
        if not isinstance(label, str):
            raise SPSDKKeyError("Label must be string")
        for item in cls.__members__.values():
            if item.label.upper() == label.upper():
                return item
        raise SPSDKKeyError(
            f"There is no {cls.__name__} item with label {label} defined"
        )
