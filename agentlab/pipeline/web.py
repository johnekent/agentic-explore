from __future__ import annotations
from dataclasses import dataclass
from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import quote_plus, urlparse
from ddgs import DDGS

@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str

def ddg_html_search(query: str, top_n: int = 10) -> list[SearchHit]:
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=top_n)
        hits: list[SearchHit] = []
        for r in results:
            hits.append(SearchHit(title=r['title'], url=r['href'], snippet=r.get('body', '')))
        return hits

def extract_readable_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body
    text = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines[:4000])

def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""
