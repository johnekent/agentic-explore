from ddgs import DDGS

with DDGS() as ddgs:
    results = ddgs.text(
        "asset tokenization market infrastructure",
        max_results=10
    )
    for r in results:
        print(r["title"], r["href"])