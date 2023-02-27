# SPDX-FileCopyrightText: 2022-present Jamie Watts <jamie@betwatch.com>
#
# SPDX-License-Identifier: MIT

import os
from typing import Optional

from .client import BetwatchClient
from .client_async import BetwatchAsyncClient


async def connect_async(api_key: Optional[str] = None) -> BetwatchAsyncClient:
    """Connect to the Betwatch GraphQL API."""

    # check for env var if no api key is provided
    if api_key is None:
        api_key = os.getenv("BETWATCH_API_KEY")
        if api_key is None:
            raise ValueError("No API key provided.")

    client = BetwatchAsyncClient(api_key=api_key)
    return client


def connect(api_key: Optional[str] = None) -> BetwatchClient:
    """Connect to the Betwatch GraphQL API."""

    # check for env var if no api key is provided
    if api_key is None:
        api_key = os.getenv("BETWATCH_API_KEY")
        if api_key is None:
            raise ValueError("No API key provided.")

    client = BetwatchClient(api_key=api_key)
    return client
