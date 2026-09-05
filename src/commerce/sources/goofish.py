from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlencode

from commerce.domain import ProductRef, ProductSnapshot


SEARCH_API_MARKER = "mtop.taobao.idlemtopsearch.pc.search"
DETAIL_API_MARKER = "mtop.taobao.idle.pc.detail"


class GoofishSourceError(RuntimeError):
    """Base error for Goofish acquisition failures."""


class GoofishAuthError(GoofishSourceError):
    """Raised when the captured browser session is no longer authenticated."""


class GoofishCaptureError(GoofishSourceError):
    """Raised when the expected network JSON cannot be captured."""


class GoofishTransport(Protocol):
    async def search(self, query: str) -> dict[str, Any]: ...

    async def detail(self, product: ProductRef) -> dict[str, Any]: ...


@dataclass(frozen=True)
class GoofishSearchItem:
    product: ProductRef
    price: float | None
    wants_count: float | None
    published_at: datetime | None
    raw: dict[str, Any]


def _dig(value: Any, *path: str, default: Any = None) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _parse_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "").replace("¥", "")
    if not text or text.lower() in {"nan", "none", "n/a", "-", "暂无", "未知"}:
        return None

    multiplier = 1.0
    if "万" in text:
        multiplier = 10000.0
        text = text.replace("万", "")

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0)) * multiplier


def _parse_epoch(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if numeric > 10_000_000_000:
        numeric /= 1000.0
    try:
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    epoch = _parse_epoch(value)
    if epoch is not None:
        return epoch
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_price_parts(value: Any) -> float | None:
    if isinstance(value, list):
        value = "".join(
            str(part.get("text", ""))
            for part in value
            if isinstance(part, dict)
        ).replace("当前价", "")
    return _parse_number(value)


def _normalize_url(value: Any, external_id: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("fleamarket://"):
        raw = raw.replace("fleamarket://", "https://www.goofish.com/", 1)
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"https://www.goofish.com/item?id={external_id}"


def parse_search_response(payload: dict[str, Any]) -> list[GoofishSearchItem]:
    """Parse the JSON emitted by Goofish's own search network request."""

    result_list = _dig(payload, "data", "resultList", default=[])
    if not isinstance(result_list, list):
        return []

    parsed: list[GoofishSearchItem] = []
    seen: set[str] = set()
    for entry in result_list:
        main = _dig(entry, "data", "item", "main", "exContent", default={})
        click_args = _dig(
            entry,
            "data",
            "item",
            "main",
            "clickParam",
            "args",
            default={},
        )
        if not isinstance(main, dict):
            continue
        if not isinstance(click_args, dict):
            click_args = {}

        external_id = str(
            _first_present(main.get("itemId"), click_args.get("itemId"), "")
        ).strip()
        if not external_id or external_id in seen:
            continue

        seen.add(external_id)
        title = str(main.get("title") or "").strip() or None
        target_url = _dig(entry, "data", "item", "main", "targetUrl", default="")
        product = ProductRef(
            source="goofish",
            external_id=external_id,
            url=_normalize_url(target_url, external_id),
            title=title,
        )
        parsed.append(
            GoofishSearchItem(
                product=product,
                price=_parse_price_parts(main.get("price")),
                wants_count=_parse_number(click_args.get("wantNum")),
                published_at=_parse_datetime(click_args.get("publishTime")),
                raw={
                    "entry": entry,
                    "seller_nickname": main.get("userNickName"),
                    "region": main.get("area"),
                    "image_url": main.get("picUrl"),
                    "original_price": main.get("oriPrice"),
                },
            )
        )

    return parsed


def parse_detail_response(
    payload: dict[str, Any],
    *,
    product: ProductRef,
    seed: GoofishSearchItem | None = None,
    observed_at: datetime | None = None,
) -> ProductSnapshot:
    """Convert a Goofish detail API response into platform-neutral facts."""

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = {}
    item = data.get("itemDO")
    seller = data.get("sellerDO")
    item = item if isinstance(item, dict) else {}
    seller = seller if isinstance(seller, dict) else {}

    price = _parse_number(
        _first_present(
            item.get("soldPrice"),
            item.get("price"),
            _dig(item, "priceInfo", "price"),
            seed.price if seed else None,
        )
    )
    wants_count = _parse_number(
        _first_present(
            item.get("wantCnt"),
            seed.wants_count if seed else None,
        )
    )
    views_count = _parse_number(item.get("browseCnt"))

    published_at = _parse_datetime(
        _first_present(
            item.get("publishTime"),
            item.get("gmtCreate"),
            seed.published_at if seed else None,
        )
    )

    title = str(
        _first_present(
            item.get("title"),
            item.get("itemTitle"),
            product.title,
            seed.product.title if seed else None,
            "",
        )
    ).strip() or None

    image_infos = item.get("imageInfos")
    image_urls = []
    if isinstance(image_infos, list):
        image_urls = [
            str(image.get("url"))
            for image in image_infos
            if isinstance(image, dict) and image.get("url")
        ]

    return ProductSnapshot(
        source="goofish",
        external_id=product.external_id,
        observed_at=observed_at or datetime.now(timezone.utc),
        url=product.url,
        title=title,
        price=price,
        sales_count=None,
        views_count=views_count,
        wants_count=wants_count,
        reviews_count=None,
        rating=None,
        rank=None,
        stock=None,
        seller_count=None,
        published_at=published_at,
        raw={
            "search": seed.raw if seed else None,
            "detail": {"itemDO": item, "sellerDO": seller},
            "seller": {
                "id": _first_present(
                    seller.get("sellerId"),
                    seller.get("userId"),
                ),
                "nickname": _first_present(
                    seller.get("nick"),
                    seller.get("userNick"),
                    seller.get("displayName"),
                ),
                "zhima_level": _dig(seller, "zhimaLevelInfo", "levelName"),
                "registration_days": seller.get("userRegDay"),
            },
            "image_urls": image_urls,
        },
    )


def _is_login_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "passport.goofish.com" in lowered or "mini_login" in lowered


def _load_storage_state(path: str) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        raise FileNotFoundError(f"Goofish state file does not exist: {path}")

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Goofish state file must contain a JSON object")

    storage = payload.get("storage")
    if isinstance(storage, dict) and "cookies" in storage:
        return storage

    cookies = payload.get("cookies", [])
    origins = payload.get("origins", [])
    if not isinstance(cookies, list):
        raise ValueError("Goofish state file cookies must be a list")
    if not isinstance(origins, list):
        origins = []
    return {"cookies": cookies, "origins": origins}


class PlaywrightGoofishTransport:
    """Capture the JSON requests emitted by the authenticated Goofish web UI.

    The browser is used only to establish a real session and trigger requests.
    Parsing stays in pure functions so it can be tested independently.
    """

    def __init__(
        self,
        state_file: str,
        *,
        headless: bool = True,
        timeout_ms: int = 30_000,
    ) -> None:
        self.state_file = state_file
        self.headless = headless
        self.timeout_ms = timeout_ms

    async def search(self, query: str) -> dict[str, Any]:
        search_url = f"https://www.goofish.com/search?{urlencode({'q': query})}"
        return await self._capture(search_url, SEARCH_API_MARKER)

    async def detail(self, product: ProductRef) -> dict[str, Any]:
        return await self._capture(product.url, DETAIL_API_MARKER)

    async def _capture(self, url: str, marker: str) -> dict[str, Any]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for live Goofish capture. "
                "Install commerce-intelligence[goofish] and run "
                "`playwright install chromium`."
            ) from exc

        storage_state = _load_storage_state(self.state_file)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=storage_state,
                locale="zh-CN",
            )
            page = await context.new_page()
            try:
                async with page.expect_response(
                    lambda response: marker in response.url,
                    timeout=self.timeout_ms,
                ) as response_info:
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self.timeout_ms,
                    )

                if _is_login_url(page.url):
                    raise GoofishAuthError(
                        f"Goofish login state is invalid; redirected to {page.url}"
                    )

                response = await response_info.value
                if not response.ok:
                    raise GoofishCaptureError(
                        f"Goofish network request failed with HTTP {response.status}"
                    )
                payload = await response.json()
                if not isinstance(payload, dict):
                    raise GoofishCaptureError("Goofish response was not a JSON object")
                return payload
            except GoofishSourceError:
                raise
            except Exception as exc:
                if _is_login_url(page.url):
                    raise GoofishAuthError(
                        f"Goofish login state is invalid; redirected to {page.url}"
                    ) from exc
                raise GoofishCaptureError(
                    f"Could not capture Goofish network response containing {marker}"
                ) from exc
            finally:
                await context.close()
                await browser.close()


class GoofishSourceAdapter:
    name = "goofish"

    def __init__(
        self,
        transport: GoofishTransport | None = None,
        *,
        state_file: str | None = None,
        headless: bool | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if transport is None:
            resolved_state_file = state_file or os.getenv("GOOFISH_STATE_FILE")
            if not resolved_state_file:
                raise ValueError(
                    "state_file or GOOFISH_STATE_FILE is required for live capture"
                )
            resolved_headless = headless
            if resolved_headless is None:
                resolved_headless = (
                    os.getenv("GOOFISH_HEADLESS", "true").strip().lower()
                    not in {"false", "0", "no", "off"}
                )
            transport = PlaywrightGoofishTransport(
                resolved_state_file,
                headless=resolved_headless,
            )
        self.transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._search_cache: dict[str, GoofishSearchItem] = {}

    async def discover(self, query: str, *, limit: int = 100) -> list[ProductRef]:
        if limit <= 0:
            return []
        payload = await self.transport.search(query)
        items = parse_search_response(payload)
        selected = items[:limit]
        for item in selected:
            self._search_cache[item.product.external_id] = item
        return [item.product for item in selected]

    async def snapshot(self, product: ProductRef) -> ProductSnapshot:
        if product.source != self.name:
            raise ValueError(
                f"GoofishSourceAdapter cannot snapshot source {product.source!r}"
            )
        payload = await self.transport.detail(product)
        return parse_detail_response(
            payload,
            product=product,
            seed=self._search_cache.get(product.external_id),
            observed_at=self._clock(),
        )
