from typing import TypedDict, Literal
from datetime import datetime

Direction = Literal["incoming", "outgoing", "unknown"]


class MCPMessageLog(TypedDict):
    timestamp: datetime
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    direction: Direction
    message: str
