# SPDX-FileCopyrightText: 2022-present Jamie Watts <jamie@betwatch.com>
#
# SPDX-License-Identifier: MIT

from .client import BetwatchClient
from .client_async import BetwatchAsyncClient

# export the version
from .__about__ import __version__
