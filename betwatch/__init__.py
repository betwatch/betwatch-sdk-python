# SPDX-FileCopyrightText: 2022-present Jamie Watts <jamie@betwatch.com>
#
# SPDX-License-Identifier: MIT

from .client import BetwatchClient
from .client_async import BetwatchAsyncClient


async def connect_async(api_key: str) -> BetwatchAsyncClient:
    """Connect to the Betwatch GraphQL API."""
    client = BetwatchAsyncClient(api_key=api_key)
    return client


def connect(api_key: str) -> BetwatchClient:
    """Connect to the Betwatch GraphQL API."""
    client = BetwatchClient(api_key=api_key)
    return client
