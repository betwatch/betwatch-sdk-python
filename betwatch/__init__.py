# SPDX-FileCopyrightText: 2022-present Jamie Watts <jamie@betwatch.com>
#
# SPDX-License-Identifier: MIT

import os
from typing import Optional

from .client import BetwatchClient
from .client_async import BetwatchAsyncClient


def connect_async(api_key: Optional[str] = None) -> BetwatchAsyncClient:
    """Connect to the Betwatch GraphQL API."""
    return BetwatchAsyncClient(api_key)


def connect(api_key: Optional[str] = None) -> BetwatchClient:
    """Connect to the Betwatch GraphQL API."""
    return BetwatchClient(api_key)
