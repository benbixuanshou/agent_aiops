"""Web search tool — DuckDuckGo, no API key required."""

import logging
import re
from urllib.parse import quote

import httpx
from langchain_core.tools import tool

logger = logging.getLogger("superbizagent")


@tool
def web_search(query: str) -> str:
    """联网搜索，获取最新的公开信息。仅在内部知识库找不到答案时使用。

    Args:
        query: 搜索关键词

    Returns:
        搜索结果摘要列表，每项含标题、摘要和链接
    """
    try:
        resp = httpx.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            headers={"User-Agent": "SuperBizAgent/2.0"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("web_search: request failed for '%s': %s", query, e)
        return f"联网搜索失败: {e}"

    html = resp.text
    results = _parse_lite_results(html)

    if not results:
        return f"未找到与「{query}」相关的网络搜索结果。"

    lines = [f"联网搜索「{query}」找到 {len(results)} 条结果:\n"]
    for r in results[:5]:
        lines.append(f"  [{r['title']}]({r['link']})")
        lines.append(f"    {r['snippet']}\n")

    lines.append("\n请注意：以上结果来自公开网络搜索，非内部知识库。")
    return "\n".join(lines)


def _parse_lite_results(html: str) -> list[dict]:
    """Parse DuckDuckGo Lite search results."""
    results = []
    # DuckDuckGo Lite returns results in <a> links with class="result-link" and <td> snippets
    # Pattern: each result is a table row with link + description
    links = re.findall(
        r'<a[^>]*rel="nofollow"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
        html, re.IGNORECASE
    )
    snippets = re.findall(
        r'<td class="result-snippet"[^>]*>(.*?)</td>',
        html, re.DOTALL | re.IGNORECASE
    )

    for i in range(min(len(links), len(snippets))):
        snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
        # Decode HTML entities
        snippet = snippet.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        title = links[i][1].strip()
        title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        results.append({
            "title": title,
            "link": links[i][0],
            "snippet": snippet[:300] if snippet else "(无摘要)",
        })

    return results
