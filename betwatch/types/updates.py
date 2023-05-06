from typing import TypedDict, Union


class SelectionData(TypedDict):
    selection_id: str
    value: Union[str, int, float]
