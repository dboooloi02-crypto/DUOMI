#!/usr/bin/env python3

import sys
import json
import re
import html

from web_open import web_open


RASPBERRY_PI_RSS = "https://www.raspberrypi.com/news/feed/"

LATEST_KEYWORDS = re.compile(
    r"最新|新闻|消息|最近|更新|latest|news|recent",
    re.IGNORECASE
)

RASPBERRY_PI_KEYWORDS = re.compile(
    r"树莓派|raspberry\s*pi",
    re.IGNORECASE
)


def is_raspberry_pi_news_query(query):
    if not isinstance(query, str):
        return False

    return bool(
        RASPBERRY_PI_KEYWORDS.search(query)
        and LATEST_KEYWORDS.search(query)
    )


def clean_html_text(text):
    if not text:
        return ""

    text = html.unescape(text)

    # 去掉 HTML 标签
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    # 压缩空白
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def get_raspberry_pi_news(limit=5):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5

    limit = max(
        1,
        min(limit, 10)
    )

    result = web_open(
        RASPBERRY_PI_RSS,
        max_chars=20000
    )

    if not result.get("success"):
        return {
            "success": False,
            "source": RASPBERRY_PI_RSS,
            "error": result.get(
                "error",
                "读取 RSS 失败"
            )
        }

    items = result.get(
        "items",
        []
    )[:limit]

    news = []

    for item in items:
        news.append({
            "title": item.get(
                "title",
                ""
            ).strip(),

            "url": item.get(
                "link",
                ""
            ).strip(),

            "published": item.get(
                "published",
                ""
            ).strip(),

            "summary": clean_html_text(
                item.get(
                    "description",
                    ""
                )
            )
        })

    return {
        "success": True,
        "source": RASPBERRY_PI_RSS,
        "source_type": "official_rss",
        "feed_title": result.get(
            "feed_title",
            "News - Raspberry Pi"
        ),
        "count": len(news),
        "items": news
    }


def get_news_for_query(
    query,
    limit=5
):
    if not is_raspberry_pi_news_query(query):
        return {
            "success": False,
            "matched": False,
            "query": query,
            "error": "不是 Raspberry Pi 最新新闻查询"
        }

    result = get_raspberry_pi_news(
        limit=limit
    )

    result["matched"] = True
    result["query"] = query

    return result


def main():
    if len(sys.argv) >= 2:
        query = " ".join(
            sys.argv[1:]
        )
    else:
        query = input(
            "测试查询："
        ).strip()

    print("DUOMI Web News V0.1")
    print(
        f"查询：{query}"
    )

    result = get_news_for_query(
        query,
        limit=5
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
