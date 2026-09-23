#!/usr/bin/env python3

import sys
import json
import gzip
import re
import html
import urllib.parse
import urllib.request
import urllib.error


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) "
    "AppleWebKit/537.36 "
    "Chrome/137 Safari/537.36"
)


def clean_text(value):
    if not value:
        return ""

    value = html.unescape(value)

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def parse_baidu_results(raw_html, max_results=5):
    """
    解析百度当前 PC 搜索结果。

    百度结果容器中常见：
        mu="https://真实目标网址"

    h3 中的 href 通常是：
        http://www.baidu.com/link?url=...

    优先使用 mu，百度跳转链接只作为备用。
    """

    results = []

    # 找到所有带 mu 属性的 div。
    # 每一个 mu 到下一个 mu 之间，通常对应一个结果块。
    mu_pattern = re.compile(
        r'<div\b[^>]*\bmu=["\']'
        r'(https?://[^"\']+)'
        r'["\'][^>]*>',
        re.IGNORECASE
    )

    mu_matches = list(
        mu_pattern.finditer(raw_html)
    )

    for index, mu_match in enumerate(mu_matches):

        if len(results) >= max_results:
            break

        direct_url = html.unescape(
            mu_match.group(1)
        )

        block_start = mu_match.start()

        if index + 1 < len(mu_matches):
            block_end = mu_matches[index + 1].start()
        else:
            block_end = len(raw_html)

        block = raw_html[
            block_start:block_end
        ]

        # 必须存在 h3，才把它视为普通搜索结果
        h3_match = re.search(
            r'<h3\b[^>]*>'
            r'.*?'
            r'<a\b[^>]*'
            r'href=["\']'
            r'(https?://[^"\']+)'
            r'["\'][^>]*>'
            r'(.*?)'
            r'</a>'
            r'.*?'
            r'</h3>',
            block,
            re.IGNORECASE | re.DOTALL
        )

        if not h3_match:
            continue

        wrapped_url = html.unescape(
            h3_match.group(1)
        )

        title = clean_text(
            h3_match.group(2)
        )

        if not title:
            continue

        # 找摘要
        summary_match = re.search(
            r'data-module=["\']abstract["\']'
            r'.*?'
            r'<span\b[^>]*'
            r'class=["\'][^"\']*summary-text[^"\']*["\']'
            r'[^>]*>'
            r'(.*?)'
            r'</span>',
            block,
            re.IGNORECASE | re.DOTALL
        )

        summary = ""

        if summary_match:
            summary = clean_text(
                summary_match.group(1)
            )

        # mu 优先作为真实目标地址。
        # 如果 mu 本身明显是百度内部运营模块，
        # 则保留百度跳转地址。
        direct_host = ""

        try:
            direct_host = urllib.parse.urlparse(
                direct_url
            ).netloc.lower()
        except Exception:
            pass

        internal_patterns = (
            "recommend_list.baidu.com",
            "top.baidu.com",
            "nourl.ubs.baidu.com",
            "bdstatic.com",
            "bcebos.com",
            "baidu.com/favicon",
        )

        is_internal = any(
            pattern in direct_host
            for pattern in internal_patterns
        )

        final_url = (
            wrapped_url
            if is_internal
            else direct_url
        )

        # 去重
        duplicate = False

        for old in results:
            if (
                old["url"] == final_url
                or old["title"] == title
            ):
                duplicate = True
                break

        if duplicate:
            continue

        results.append({
            "title": title,
            "url": final_url,
            "snippet": summary,
            "source": "baidu",
            "baidu_redirect_url": wrapped_url,
        })

    return results


def fetch_baidu(
    query,
    max_results=5,
    timeout=8
):
    params = urllib.parse.urlencode({
        "wd": query
    })

    url = (
        "https://www.baidu.com/s?"
        + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "*/*;q=0.8"
            ),
            "Accept-Encoding": "gzip, deflate"
        }
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout
        ) as response:

            raw = response.read()

            content_encoding = (
                response.headers
                .get(
                    "Content-Encoding",
                    ""
                )
                .lower()
            )

            if "gzip" in content_encoding:
                raw = gzip.decompress(raw)

            final_url = response.geturl()

        text = raw.decode(
            "utf-8",
            errors="replace"
        )

        results = parse_baidu_results(
            text,
            max_results=max_results
        )

        return {
            "success": True,
            "query": query,
            "backend": "baidu",
            "url": url,
            "final_url": final_url,
            "result_count": len(results),
            "results": results
        }

    except urllib.error.HTTPError as exc:

        return {
            "success": False,
            "query": query,
            "backend": "baidu",
            "status_code": exc.code,
            "error": (
                f"HTTP {exc.code}: "
                f"{exc.reason}"
            )
        }

    except urllib.error.URLError as exc:

        return {
            "success": False,
            "query": query,
            "backend": "baidu",
            "error": (
                f"网络错误: {exc.reason}"
            )
        }

    except Exception as exc:

        return {
            "success": False,
            "query": query,
            "backend": "baidu",
            "error": (
                f"未知错误: {exc}"
            )
        }


def main():

    if len(sys.argv) >= 2:
        query = " ".join(
            sys.argv[1:]
        )
    else:
        query = input(
            "测试搜索："
        ).strip()

    print(
        "DUOMI Baidu Search V0.1"
    )

    print(
        "查询：",
        query
    )

    result = fetch_baidu(
        query,
        max_results=5
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
