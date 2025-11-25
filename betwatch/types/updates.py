from typing import TypedDict


class SelectionData(TypedDict):
    selection_id: str
    value: str | int | float
