from __future__ import annotations

from typing import Protocol

from commerce.domain import ProductSnapshot


class SnapshotRepository(Protocol):
    def save(self, snapshot: ProductSnapshot) -> None: ...

    def list_for_product(self, source: str, external_id: str) -> list[ProductSnapshot]: ...
