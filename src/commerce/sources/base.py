from __future__ import annotations

from typing import Protocol

from commerce.domain import ProductRef, ProductSnapshot


class ProductSourceAdapter(Protocol):
    """Platform boundary for discovery and fact collection.

    Implementations may use official APIs, HTTP endpoints, browser-network
    capture, AnyCrawl, or browser automation. The domain layer never depends on
    those transport details.
    """

    name: str

    async def discover(self, query: str, *, limit: int = 100) -> list[ProductRef]: ...

    async def snapshot(self, product: ProductRef) -> ProductSnapshot: ...
