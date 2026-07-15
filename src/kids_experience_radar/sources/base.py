from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Iterable

from ..http import PoliteHttpClient
from ..models import CrawlWindow, Event


@dataclass(slots=True, frozen=True)
class SourceInfo:
    source_id: str
    name: str
    owner: str
    source_type: str
    official_url: str
    license_code: str | None
    requires_key: str | None = None
    enabled_by_default: bool = True
    policy_status: str = "approved_api"
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Source(ABC):
    info: SourceInfo

    @abstractmethod
    def crawl(self, client: PoliteHttpClient, window: CrawlWindow) -> Iterable[Event]:
        raise NotImplementedError

    def available(self) -> tuple[bool, str | None]:
        return True, None
