from dataclasses import dataclass, field
from typing import Any, Optional, Union
from datetime import datetime


@dataclass
class AgentMessage:
    from_agent: str
    to_agent: Union[str, list]
    pipeline_id: str
    payload: dict
    status: str = "success"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None


class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    def log(self, msg: str):
        print(f"[{self.name}] {msg}")

    def create_message(
        self,
        to: Union[str, list],
        pipeline_id: str,
        payload: dict,
        status: str = "success",
        error: Optional[str] = None,
    ) -> AgentMessage:
        return AgentMessage(
            from_agent=self.name,
            to_agent=to,
            pipeline_id=pipeline_id,
            payload=payload,
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            error=error,
        )
