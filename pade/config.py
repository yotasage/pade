
from dataclasses import dataclass

@dataclass
class Config:
    skillbridge_id: str | int | None = "default"

config = Config()
