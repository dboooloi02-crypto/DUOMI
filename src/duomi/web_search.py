import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from web_search_baidu import fetch_baidu


BING_URL = "https://www.bing.com/search"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137 Safari/537.36"
)


class BingResultParser(HTMLParser):
    """
    解析 Bing 搜索结果中的：
    - 标题
    - URL
    - 摘要
    """

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.results = []
        self.current = None

        self.in_result = False
        self.in_h2 = False
        self.in_title = False
        self.in_snippet = False

        self.title_parts = []
        self.snippet_parts = []

    @staticmethod
    def _class_contains(attrs, class_name):
        for key, value in attrs:
            if key == "class" and value:
                return class_name in value.split()

        return False

    def handle_starttag(self, tag, attrs):
        if tag == "li" and self._class_contains(
            attrs,
            "b_algo"
        ):
            if self.current:
                self._finish_result()

            self.in_result = True

            self.current = {
                "title": "",
                "url": "",
                "snippet": "",
            }

            self.title_parts = []
            self.snippet_parts = []

            return

        if not self.in_result:
            return

        if tag == "h2":
            self.in_h2 = True
            return

        if (
            self.in_h2
            and tag == "a"
            and self.current is not None
        ):
            href = ""

            for key, value in attrs:
                if key == "href":
                    href = value or ""
                    break

            self.current["url"] = href
            self.in_title = True
            return

        if tag == "p" and self._class_contains(
            attrs,
            "b_lineclamp2"
        ):
            self.in_snippet = True

    def handle_data(self, data):
        if not self.in_result:
            return

        if self.in_title:
            self.title_parts.append(data)

        if self.in_snippet:
            self.snippet_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            self.in_title = False

        if tag == "h2":
            self.in_h2 = False

        if tag == "p" and self.in_snippet:
            self.in_snippet = False

        if tag == "li" and self.in_result:
            self._finish_result()

    def _finish_result(self):
        if self.current is None:
            return

        title = " ".join(
            "".join(self.title_parts).split()
        )

        snippet = " ".join(
            "".join(self.snippet_parts).split()
        )

        url = self.current.get(
            "url",
            ""
        ).strip()

        if title or url or snippet:
            self.current["title"] = title
            self.current["snippet"] = snippet
            self.current["url"] = url

            self.results.append(
                self.current
            )

        self.current = None
        self.in_result = False
        self.in_h2 = False
        self.in_title = False
        self.in_snippet = False
        self.title_parts = []
        self.snippet_parts = []


def _now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_query(query):
    """
    对搜索关键词做语义增强。

    特别处理“树莓派”：
    Bing 有时会把“树莓派”理解为水果，
    所以涉及 Raspberry Pi 时直接使用英文主体名称。
    """

    query = str(query).strip()

    if not query:
        return ""

    lower = query.lower()

    # -----------------------------------------------------
    # Raspberry Pi 特殊处理
    # -----------------------------------------------------
    if "树莓派" in query:

        remainder = query.replace(
            "树莓派",
            ""
        ).strip()

        if not remainder:
            query = "Raspberry Pi"
        else:
            query = f"Raspberry Pi {remainder}"

        lower = query.lower()

    # -----------------------------------------------------
    # 最新信息增加当前年份
    # -----------------------------------------------------
    latest_words = [
        "最新",
        "最近",
        "目前",
        "现在",
        "今年",
        "latest",
        "recent",
        "now",
        "current",
    ]

    has_latest_word = any(
        word in lower
        for word in latest_words
    )

    # 修正为真正的四位年份匹配
    has_year = bool(
        re.search(
            r"20\d{2}",
            query
        )
    )

    if has_latest_word and not has_year:
        query = (
            query
            + f" {datetime.now().year}"
        )

    return query.strip()


def _fetch_bing(query, max_results=5):
    params = urlencode({
        "q": query,
        "setlang": "zh-CN",
        "cc": "CN",
        "form": "QBLH",
    })

    url = f"{BING_URL}?{params}"

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
            "Accept-Language": (
                "zh-CN,zh;q=0.9,en;q=0.8"
            ),
        },
    )

    with urlopen(
        request,
        timeout=8
    ) as response:

        raw = response.read(
            512 * 1024
        )

        charset = (
            response.headers.get_content_charset()
            or "utf-8"
        )

    html = raw.decode(
        charset,
        errors="replace"
    )

    parser = BingResultParser()
    parser.feed(html)

    results = []

    seen_urls = set()

    for item in parser.results:

        url = item["url"].strip()

        if (
            not url
            or url in seen_urls
        ):
            continue

        seen_urls.add(url)

        results.append({
            "title": item["title"],
            "url": url,
            "snippet": item["snippet"],
            "source": "bing",
        })

        if len(results) >= max_results:
            break

    return results


def _fetch_backend(
    backend,
    query,
    max_results
):
    """
    单独执行一个搜索后端。
    返回：
        backend, results, error
    """

    try:

        if backend == "bing":

            results = _fetch_bing(
                query,
                max_results=max_results
            )

        elif backend == "baidu":

            result = fetch_baidu(
                query,
                max_results=max_results,
                timeout=8
            )

            if not result.get(
                "success",
                False
            ):
                return (
                    backend,
                    [],
                    result.get(
                        "error",
                        "百度搜索失败"
                    )
                )

            results = result.get(
                "results",
                []
            )

        else:

            return (
                backend,
                [],
                f"未知后端：{backend}"
            )

        return (
            backend,
            results,
            None
        )

    except Exception as exc:

        return (
            backend,
            [],
            str(exc)
        )


def _is_chinese_query(query):
    return bool(
        re.search(
            r"[\u4e00-\u9fff]",
            query
        )
    )


def _canonical_url(url):
    """
    用于去重。
    不改变实际返回 URL。
    """

    if not url:
        return ""

    value = str(url).strip()

    # 去掉尾部 /
    value = value.rstrip("/")

    return value.lower()



def _is_low_quality_result(title, url, snippet):
    """
    过滤明显不是知识网页的搜索结果：
    - 百度图片/视频
    - 搜索结果页
    - 空白结果
    """
    title_text = str(title or "").strip().lower()
    url_text = str(url or "").strip().lower()
    snippet_text = str(snippet or "").strip()

    if not title_text and not url_text and not snippet_text:
        return True

    # 明确的搜索结果页/媒体搜索页
    bad_url_parts = [
        "image.baidu.com/search",
        "video.baidu.com/search",
        "www.baidu.com/s?",
        "/search?query=",
        "/search?q=",
        "/search?keyword=",
    ]

    for bad_part in bad_url_parts:
        if bad_part in url_text:
            return True

    # 明确的搜索页标题
    bad_title_parts = [
        "百度图片",
        "百度视频",
        "搜索结果",
        "搜索结果页",
    ]

    for bad_part in bad_title_parts:
        if bad_part in title_text:
            return True

    return False


def _extract_query_terms(query):
    """
    提取简单的中英文查询词。
    不依赖第三方分词库。
    """
    query = str(query or "").strip().lower()

    terms = []

    # 英文/数字词
    english_terms = re.findall(
        r"[a-z0-9][a-z0-9._+-]*",
        query
    )

    for term in english_terms:
        if len(term) >= 2:
            terms.append(term)

    # 针对中文提取2~4字短语
    chinese_parts = re.findall(
        r"[\u4e00-\u9fff]+",
        query
    )

    for part in chinese_parts:
        if len(part) >= 2:
            for size in (2, 3, 4):
                for i in range(
                    0,
                    len(part) - size + 1
                ):
                    piece = part[i:i + size]
                    if piece not in terms:
                        terms.append(piece)

    return terms



def _classify_source(url):
    """
    根据域名做简单来源类型识别。
    这是来源提示，不是事实可信度评分。
    """

    value = str(url or "").strip().lower()

    if not value:
        return "unknown"

    try:
        from urllib.parse import urlparse
        hostname = (
            urlparse(value).hostname
            or ""
        ).lower()
    except Exception:
        hostname = ""

    # 官方来源
    official_domains = [
        "raspberrypi.com",
        "raspberrypi.org",
        "deepseek.com",
        "openai.com",
    ]

    # 官方文档/开发者资料
    documentation_domains = [
        "docs.python.org",
        "developer.mozilla.org",
        "docs.github.com",
        "github.com",
    ]

    # 搜索/聚合页面
    search_domains = [
        "baidu.com",
        "bing.com",
        "google.com",
        "duckduckgo.com",
    ]

    # 常见媒体
    media_domains = [
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "nytimes.com",
        "techcrunch.com",
        "theverge.com",
    ]

    for domain in official_domains:
        if (
            hostname == domain
            or hostname.endswith("." + domain)
        ):
            return "official"

    for domain in documentation_domains:
        if (
            hostname == domain
            or hostname.endswith("." + domain)
        ):
            return "documentation"

    for domain in media_domains:
        if (
            hostname == domain
            or hostname.endswith("." + domain)
        ):
            return "media"

    for domain in search_domains:
        if (
            hostname == domain
            or hostname.endswith("." + domain)
        ):
            return "search"

    # 常见中文社区/博客平台
    community_domains = [
        "csdn.net",
        "cnblogs.com",
        "jianshu.com",
        "zhihu.com",
        "juejin.cn",
        "segmentfault.com",
        "51cto.com",
    ]

    for domain in community_domains:
        if (
            hostname == domain
            or hostname.endswith("." + domain)
        ):
            return "community"

    return "unknown"


def _relevance_score(query, title, snippet, url):
    """
    简单相关性评分：
    - 标题命中权重高
    - 摘要其次
    - Raspberry Pi 作为整体短语给予额外权重
    """
    query_text = str(query or "").strip().lower()
    title_text = str(title or "").strip().lower()
    snippet_text = str(snippet or "").strip().lower()
    url_text = str(url or "").strip().lower()

    searchable = (
        f"{title_text} {snippet_text} {url_text}"
    )

    score = 0

    # 对完整技术短语提高权重
    phrase_rules = [
        ("raspberry pi", 8),
        ("gpio", 6),
        ("l298n", 8),
        ("电机", 6),
        ("马达", 5),
        ("控制", 4),
        ("pwm", 5),
    ]

    for phrase, weight in phrase_rules:
        if phrase in query_text and phrase in searchable:
            if phrase in title_text:
                score += weight * 2
            elif phrase in snippet_text:
                score += weight
            else:
                score += 1

    # 一般查询词
    for term in _extract_query_terms(query_text):
        if term in title_text:
            score += 3
        elif term in snippet_text:
            score += 1
        elif term in url_text:
            score += 1

    return score


def _merge_results(
    backend_results,
    query,
    max_results
):
    """
    多来源结果合并 + 过滤 + 相关性排序。

    backend_results:
        [
            ("baidu", [...]),
            ("bing", [...])
        ]
    """

    candidates = []

    seen_urls = set()
    seen_titles = set()

    for backend, results in backend_results:

        for item in results:

            title = str(
                item.get(
                    "title",
                    ""
                )
            ).strip()

            url = str(
                item.get(
                    "url",
                    ""
                )
            ).strip()

            snippet = str(
                item.get(
                    "snippet",
                    ""
                )
            ).strip()

            if _is_low_quality_result(
                title,
                url,
                snippet
            ):
                continue

            if not title and not url:
                continue

            canonical_url = _canonical_url(
                url
            )

            title_key = (
                re.sub(
                    r"\s+",
                    " ",
                    title
                )
                .strip()
                .lower()
            )

            # URL去重
            if canonical_url and (
                canonical_url in seen_urls
            ):
                continue

            # 标题去重
            if title_key and (
                title_key in seen_titles
            ):
                continue

            if canonical_url:
                seen_urls.add(
                    canonical_url
                )

            if title_key:
                seen_titles.add(
                    title_key
                )

            result = {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": item.get(
                    "source",
                    backend
                ),
                "publisher_type": _classify_source(
                    url
                ),
            }

            if item.get(
                "baidu_redirect_url"
            ):
                result[
                    "baidu_redirect_url"
                ] = item[
                    "baidu_redirect_url"
                ]

            result["_score"] = (
                _relevance_score(
                    query,
                    title,
                    snippet,
                    url
                )
            )

            result["_backend_priority"] = (
                0
                if backend == "baidu"
                else 1
            )

            candidates.append(
                result
            )

    # 相关性高的排前面；
    # 同分时保持搜索源优先级和原始顺序。
    candidates.sort(
        key=lambda item: (
            -item["_score"],
            item["_backend_priority"],
        )
    )

    final_results = []

    for item in candidates:

        item.pop(
            "_score",
            None
        )

        item.pop(
            "_backend_priority",
            None
        )

        final_results.append(
            item
        )

        if len(final_results) >= max_results:
            break

    return final_results


def web_search(
    query,
    max_results=5
):
    """
    DUOMI Web V0.4

    多搜索源互联网搜索：
    - Bing
    - Baidu

    中文查询优先百度，
    其他查询优先 Bing。
    两个后端并行执行。
    """

    original_query = str(
        query or ""
    ).strip()

    if not original_query:
        return {
            "success": False,
            "query": "",
            "results": [],
            "error": "搜索关键词为空",
        }

    normalized_query = normalize_query(
        original_query
    )

    try:

        max_results = int(
            max_results
        )

    except (
        TypeError,
        ValueError
    ):

        max_results = 5

    max_results = max(
        1,
        min(
            max_results,
            8
        )
    )

    # 中文查询优先百度，
    # 英文/其他查询优先 Bing。
    if _is_chinese_query(
        original_query
    ):
        backend_order = [
            "baidu",
            "bing",
        ]
    else:
        backend_order = [
            "bing",
            "baidu",
        ]

    backend_results_map = {}
    backend_errors = {}

    # 两个后端并行执行，避免双倍等待。
    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        backend_fetch_limit = min(
            max_results * 2,
            12
        )

        futures = {
            executor.submit(
                _fetch_backend,
                backend,
                normalized_query,
                backend_fetch_limit
            ): backend
            for backend in backend_order
        }

        for future in as_completed(
            futures
        ):

            backend = futures[
                future
            ]

            returned_backend, results, error = (
                future.result()
            )

            backend_results_map[
                returned_backend
            ] = results

            if error:
                backend_errors[
                    returned_backend
                ] = error

    ordered_results = []

    for backend in backend_order:

        ordered_results.append(
            (
                backend,
                backend_results_map.get(
                    backend,
                    []
                )
            )
        )

    results = _merge_results(
        ordered_results,
        query=normalized_query,
        max_results=max_results
    )

    successful_backends = [
        backend
        for backend in backend_order
        if backend_results_map.get(
            backend
        )
    ]

    # 两个后端都没有有效结果
    if not results:

        error_parts = []

        for backend in backend_order:

            error = backend_errors.get(
                backend
            )

            if error:
                error_parts.append(
                    f"{backend}: {error}"
                )
            else:
                error_parts.append(
                    f"{backend}: 没有有效结果"
                )

        return {
            "success": False,
            "query": original_query,
            "normalized_query": normalized_query,
            "searched_at": _now_iso(),
            "backend": "multi",
            "backends": [],
            "results": [],
            "error": (
                "；".join(
                    error_parts
                )
            ),
        }

    return {
        "success": True,
        "query": original_query,
        "normalized_query": normalized_query,
        "searched_at": _now_iso(),
        "backend": "multi",
        "backends": successful_backends,
        "result_count": len(results),
        "results": results,

        # 某个搜索引擎失败时保留错误，
        # 但不影响另一个搜索引擎的正常结果。
        "backend_errors": backend_errors,
    }


def web_search_json(
    query,
    max_results=5
):
    return json.dumps(
        web_search(
            query,
            max_results
        ),
        ensure_ascii=False,
    )


if __name__ == "__main__":

    print(
        "DUOMI Web V0.4"
    )

    query = input(
        "测试搜索："
    ).strip()

    result = web_search(
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
