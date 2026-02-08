"""Playwright-based price scraper with filtering, persistence, and reporting."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml
from playwright.async_api import async_playwright


@dataclass(frozen=True)
class Location:
    country: str
    region: str | None = None
    city: str | None = None


@dataclass(frozen=True)
class SiteTarget:
    name: str
    base_url: str
    category_paths: List[str]
    location: Location
    selectors: "SiteSelectors"
    ui_filters: "UiFilters"


@dataclass(frozen=True)
class PriceFilter:
    min_price: float
    max_price: float
    currency: str


@dataclass(frozen=True)
class TargetConfig:
    sites: List[SiteTarget]
    price_filter: PriceFilter
    categories: List[str]
    locations: List[Location]
    output_path: Path
    report_path: Path
    db_path: Path
    browser: "BrowserConfig"


@dataclass(frozen=True)
class BrowserConfig:
    headless: bool
    timeout_ms: int
    rate_limit_seconds: float
    max_retries: int
    user_agents: List[str]


@dataclass(frozen=True)
class SiteSelectors:
    product_card: str
    price: str
    title: str
    url: str
    next_page: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class UiFilters:
    price_min: str | None = None
    price_max: str | None = None
    location: str | None = None
    category: str | None = None
    apply: str | None = None
    location_value: str | None = None
    category_value: str | None = None


def load_config(path: Path) -> TargetConfig:
    raw: Dict[str, Any] = yaml.safe_load(path.read_text())
    sites: List[SiteTarget] = []
    for site in raw.get("sites", []):
        location = site.get("location", {})
        selectors = site.get("selectors", {})
        ui_filters = site.get("ui_filters", {})
        sites.append(
            SiteTarget(
                name=site["name"],
                base_url=site["base_url"],
                category_paths=site.get("category_paths", []),
                location=Location(
                    country=location.get("country"),
                    region=location.get("region"),
                    city=location.get("city"),
                ),
                selectors=SiteSelectors(
                    product_card=selectors.get("product_card", "[data-product-card]"),
                    price=selectors.get("price", "[data-price]"),
                    title=selectors.get("title", "[data-title]"),
                    url=selectors.get("url", "a"),
                    next_page=selectors.get("next_page"),
                    currency=selectors.get("currency"),
                ),
                ui_filters=UiFilters(
                    price_min=ui_filters.get("price_min"),
                    price_max=ui_filters.get("price_max"),
                    location=ui_filters.get("location"),
                    category=ui_filters.get("category"),
                    apply=ui_filters.get("apply"),
                    location_value=ui_filters.get("location_value"),
                    category_value=ui_filters.get("category_value"),
                ),
            )
        )

    price = raw.get("filters", {}).get("price", {})
    price_filter = PriceFilter(
        min_price=float(price.get("min", 0)),
        max_price=float(price.get("max", 0)),
        currency=price.get("currency", "MXN"),
    )

    categories = raw.get("filters", {}).get("categories", [])
    locations = [
        Location(
            country=item.get("country"),
            region=item.get("region"),
            city=item.get("city"),
        )
        for item in raw.get("filters", {}).get("locations", [])
    ]

    output = raw.get("output", {})
    output_path = Path(output.get("path", "data/price_results.json"))
    report_path = Path(output.get("report_path", "data/report.md"))
    db_path = Path(output.get("db_path", "data/prices.sqlite"))
    browser = raw.get("browser", {})
    browser_config = BrowserConfig(
        headless=bool(browser.get("headless", True)),
        timeout_ms=int(browser.get("timeout_ms", 20000)),
        rate_limit_seconds=float(browser.get("rate_limit_seconds", 1.5)),
        max_retries=int(browser.get("max_retries", 3)),
        user_agents=browser.get(
            "user_agents",
            [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Version/16.3 Safari/605.1.15",
            ],
        ),
    )
    return TargetConfig(
        sites=sites,
        price_filter=price_filter,
        categories=categories,
        locations=locations,
        output_path=output_path,
        report_path=report_path,
        db_path=db_path,
        browser=browser_config,
    )


def normalize_price(text: str) -> Tuple[float, Optional[str]]:
    normalized = text.replace("\u00a0", " ").strip()
    currency_match = re.search(r"(MXN|USD|EUR|\$|€|£)", normalized)
    currency = currency_match.group(1) if currency_match else None
    numbers = re.findall(r"\d+[\\d,.]*", normalized)
    if not numbers:
        raise ValueError(f"No price found in: {text}")
    candidates = []
    for number in numbers:
        if "," in number and "." in number:
            cleaned = number.replace(".", "").replace(",", ".")
        elif number.count(",") == 1 and number.count(".") == 0:
            cleaned = number.replace(",", ".")
        else:
            cleaned = number.replace(",", "")
        candidates.append(float(cleaned))
    return min(candidates), currency


def resolve_currency(price_currency: Optional[str], selector_currency: Optional[str], default: str) -> str:
    if selector_currency:
        return selector_currency
    if price_currency in {"$", "MXN"}:
        return "MXN"
    if price_currency == "USD":
        return "USD"
    if price_currency == "EUR":
        return "EUR"
    if price_currency == "£":
        return "GBP"
    return default


def within_filters(price: float, price_filter: PriceFilter) -> bool:
    return price_filter.min_price <= price <= price_filter.max_price


async def apply_ui_filters(page, ui_filters: UiFilters, price_filter: PriceFilter) -> None:
    if ui_filters.price_min:
        await page.fill(ui_filters.price_min, str(price_filter.min_price))
    if ui_filters.price_max:
        await page.fill(ui_filters.price_max, str(price_filter.max_price))
    if ui_filters.location and ui_filters.location_value:
        await page.fill(ui_filters.location, ui_filters.location_value)
    if ui_filters.category and ui_filters.category_value:
        await page.fill(ui_filters.category, ui_filters.category_value)
    if ui_filters.apply:
        await page.click(ui_filters.apply)


async def safe_goto(page, url: str, timeout_ms: int, max_retries: int) -> None:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return
        except Exception as exc:  # pylint: disable=broad-except
            last_error = exc
            await page.wait_for_timeout(1000 * (attempt + 1))
    raise RuntimeError(f"Failed to load {url}") from last_error


async def safe_text(locator) -> str:
    try:
        return await locator.inner_text()
    except Exception:  # pylint: disable=broad-except
        return ""


async def scrape_site(
    site: SiteTarget, price_filter: PriceFilter, browser_cfg: BrowserConfig
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=browser_cfg.headless)
        page = await browser.new_page(
            user_agent=random.choice(browser_cfg.user_agents),
            viewport={"width": 1280, "height": 720},
        )
        page.set_default_timeout(browser_cfg.timeout_ms)

        for path in site.category_paths:
            url = f"{site.base_url.rstrip('/')}/{path.lstrip('/')}"
            await safe_goto(page, url, browser_cfg.timeout_ms, browser_cfg.max_retries)
            await apply_ui_filters(page, site.ui_filters, price_filter)

            while True:
                cards = page.locator(site.selectors.product_card)
                count = await cards.count()
                for idx in range(count):
                    card = cards.nth(idx)
                    price_text = await safe_text(card.locator(site.selectors.price))
                    try:
                        price_value, detected_currency = normalize_price(price_text)
                    except ValueError:
                        continue
                    if not within_filters(price_value, price_filter):
                        continue

                    item_url = await card.locator(site.selectors.url).get_attribute("href")
                    title = await safe_text(card.locator(site.selectors.title))
                    results.append(
                        {
                            "site": site.name,
                            "url": item_url,
                            "title": title,
                            "category": path.split("/")[-1],
                            "location": {
                                "country": site.location.country,
                                "region": site.location.region,
                                "city": site.location.city,
                            },
                            "price": price_value,
                            "currency": resolve_currency(
                                detected_currency, site.selectors.currency, price_filter.currency
                            ),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                if not site.selectors.next_page:
                    break

                next_button = page.locator(site.selectors.next_page)
                if await next_button.count() == 0:
                    break
                if "disabled" in (await next_button.get_attribute("class") or ""):
                    break
                await next_button.click()
                await asyncio.sleep(browser_cfg.rate_limit_seconds)

        await browser.close()

    return results


def ensure_output_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def serialize_results(path: Path, items: Iterable[Dict[str, Any]]) -> None:
    ensure_output_dir(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(list(items), handle, ensure_ascii=False, indent=2)


def init_db(db_path: Path, schema_path: Path) -> None:
    ensure_output_dir(db_path)
    with sqlite3.connect(db_path) as connection:
        schema_sql = schema_path.read_text(encoding="utf-8")
        connection.executescript(schema_sql)


def persist_to_db(db_path: Path, items: Sequence[Dict[str, Any]]) -> None:
    if not items:
        return
    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO price_items (
                site, url, title, category, location_country, location_region, location_city,
                price_value, currency, is_promo, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["site"],
                    item["url"],
                    item.get("title"),
                    item["category"],
                    item["location"]["country"],
                    item["location"]["region"],
                    item["location"]["city"],
                    item["price"],
                    item["currency"],
                    0,
                    item["collected_at"],
                )
                for item in items
            ],
        )
        connection.commit()


def write_report(path: Path, items: Sequence[Dict[str, Any]]) -> None:
    ensure_output_dir(path)
    by_site: Dict[str, List[float]] = {}
    by_category: Dict[str, List[float]] = {}
    by_location: Dict[str, List[float]] = {}
    for item in items:
        by_site.setdefault(item["site"], []).append(item["price"])
        by_category.setdefault(item["category"], []).append(item["price"])
        location_key = "/".join(
            [
                item["location"]["country"],
                item["location"]["region"] or "n/a",
                item["location"]["city"] or "n/a",
            ]
        )
        by_location.setdefault(location_key, []).append(item["price"])

    lines = [
        "# Reporte de precios",
        "",
        f"Total de items: {len(items)}",
        "",
        "## Resumen por sitio",
        "",
    ]
    for site, prices in by_site.items():
        avg = sum(prices) / len(prices)
        lines.append(f"- **{site}**: {len(prices)} items, min {min(prices):.2f}, "
                     f"max {max(prices):.2f}, avg {avg:.2f}")
    lines.append("")
    lines.append("## Resumen por categoria")
    lines.append("")
    for category, prices in by_category.items():
        avg = sum(prices) / len(prices)
        lines.append(f"- **{category}**: {len(prices)} items, min {min(prices):.2f}, "
                     f"max {max(prices):.2f}, avg {avg:.2f}")
    lines.append("")
    lines.append("## Resumen por ubicacion")
    lines.append("")
    for location, prices in by_location.items():
        avg = sum(prices) / len(prices)
        lines.append(f"- **{location}**: {len(prices)} items, min {min(prices):.2f}, "
                     f"max {max(prices):.2f}, avg {avg:.2f}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


async def run_scraper(config_path: Path) -> None:
    config = load_config(config_path)
    logging.info("Starting scraper with %s sites", len(config.sites))
    all_results: List[Dict[str, Any]] = []
    for site in config.sites:
        all_results.extend(await scrape_site(site, config.price_filter, config.browser))
    serialize_results(config.output_path, all_results)
    init_db(config.db_path, Path("schema/prices.sql"))
    persist_to_db(config.db_path, all_results)
    write_report(config.report_path, all_results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Price scraper using Playwright")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/targets.yaml"),
        help="Path to YAML config with targets and filters",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    if not args.config.exists():
        raise FileNotFoundError(f"Config not found: {args.config}")

    import asyncio

    asyncio.run(run_scraper(args.config))


if __name__ == "__main__":
    main()
