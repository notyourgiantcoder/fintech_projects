"""Free, keyless research sources: Google News RSS, Economic Times RSS, SEC EDGAR,
HackerNews (Algolia), and a public-web article reader.

Everything fetched here is untrusted third-party text. Callers pass it through the
guardrails' injection scan before any of it reaches an agent.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from .. import net
from ..session import Market
from .models import Article, Filing, NewsItem, Story

_news_cache = net.TTLCache(600)
_sec_cache = net.TTLCache(6 * 3600)
_hn_cache = net.TTLCache(600)

NEWS_LOCALE: dict[Market, tuple[str, str, str]] = {
    "in": ("en-IN", "IN", "IN:en"),
    "us": ("en-US", "US", "US:en"),
}
MARKET_FEEDS: dict[Market, str] = {
    "in": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "us": "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"

MAX_ARTICLE_CHARS = 6000


class ResearchError(RuntimeError):
    pass


def _get(url: str, http: httpx.Client | None = None, **params) -> httpx.Response:
    own = http is None
    http = http or net.client()
    try:
        res = http.get(url, params=params or None, follow_redirects=True)
        res.raise_for_status()
        return res
    except httpx.HTTPError as e:
        raise ResearchError(f"{httpx.URL(url).host} didn't respond ({type(e).__name__})") from e
    finally:
        if own:
            http.close()


def _parse_feed(xml: bytes, limit: int) -> list[NewsItem]:
    feed = feedparser.parse(xml)
    items = []
    for entry in feed.entries[:limit]:
        published = None
        if entry.get("published_parsed"):
            published = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), UTC)
        source = entry.get("source", {}).get("title") if entry.get("source") else None
        items.append(
            NewsItem(
                title=entry.get("title", "").strip(),
                source=source or feed.feed.get("title"),
                link=entry.get("link", ""),
                published=published,
            )
        )
    return [i for i in items if i.title and i.link]


def search_news(
    query: str, market: Market, limit: int = 8, http: httpx.Client | None = None
) -> list[NewsItem]:
    hl, gl, ceid = NEWS_LOCALE[market]
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    return _news_cache.get_or_set(
        ("news", url, limit), lambda: _parse_feed(_get(url, http).content, limit)
    )


def market_headlines(market: Market, limit: int = 8, http: httpx.Client | None = None):
    url = MARKET_FEEDS[market]
    return _news_cache.get_or_set(
        ("headlines", url, limit), lambda: _parse_feed(_get(url, http).content, limit)
    )


def _cik_for(ticker: str, http: httpx.Client | None) -> int | None:
    def load() -> dict[str, int]:
        data = _get(SEC_TICKERS_URL, http).json()
        return {row["ticker"].upper(): int(row["cik_str"]) for row in data.values()}

    return _sec_cache.get_or_set("tickers", load).get(ticker.upper())


def recent_filings(
    ticker: str,
    forms: tuple[str, ...] = ("10-K", "10-Q", "8-K"),
    limit: int = 6,
    http: httpx.Client | None = None,
) -> list[Filing]:
    """Latest SEC filings for a US-listed company. Indian exchanges have no free equivalent."""
    cik = _cik_for(ticker, http)
    if cik is None:
        raise ResearchError(f"{ticker} isn't in SEC EDGAR (only US-listed companies are).")
    data = _sec_cache.get_or_set(
        ("subs", cik), lambda: _get(SEC_SUBMISSIONS_URL.format(cik=cik), http).json()
    )
    recent = data.get("filings", {}).get("recent", {})
    out: list[Filing] = []
    for form, filed, accession, doc, desc in zip(
        recent.get("form", []),
        recent.get("filingDate", []),
        recent.get("accessionNumber", []),
        recent.get("primaryDocument", []),
        recent.get("primaryDocDescription", []),
        strict=False,
    ):
        if form not in forms:
            continue
        folder = accession.replace("-", "")
        out.append(
            Filing(
                form=form,
                filed=filed,
                description=desc or None,
                url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{doc}",
            )
        )
        if len(out) >= limit:
            break
    return out


def search_hackernews(query: str, limit: int = 6, http: httpx.Client | None = None) -> list[Story]:
    def load() -> list[Story]:
        hits = _get(HN_SEARCH_URL, http, query=query, tags="story", hitsPerPage=limit).json()
        return [
            Story(
                title=h.get("title") or "",
                url=h.get("url"),
                points=int(h.get("points") or 0),
                comments=int(h.get("num_comments") or 0),
                created_at=h.get("created_at", ""),
                discussion_url=f"https://news.ycombinator.com/item?id={h['objectID']}",
            )
            for h in hits.get("hits", [])
            if h.get("title")
        ]

    return _hn_cache.get_or_set(("hn", query.lower(), limit), load)


def read_article(url: str, http: httpx.Client | None = None, resolve=None) -> Article:
    """Fetch a public page and extract its main text (trafilatura)."""
    import trafilatura

    try:
        res = net.fetch_public(url, http=http, resolve=resolve)
    except net.UnsafeUrlError as e:
        raise ResearchError(str(e)) from e
    except httpx.HTTPError as e:
        raise ResearchError(f"The page didn't load ({type(e).__name__}).") from e
    if res.status_code >= 400:
        raise ResearchError(f"The page returned HTTP {res.status_code}.")
    html = res.text
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    if not text.strip():
        raise ResearchError("No readable article text on that page.")
    meta = trafilatura.extract_metadata(html)
    return Article(
        url=url,
        title=meta.title if meta else None,
        text=text[:MAX_ARTICLE_CHARS],
        truncated=len(text) > MAX_ARTICLE_CHARS,
    )
