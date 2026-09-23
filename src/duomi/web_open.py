#!/usr/bin/env python3

import sys
import json
import gzip
import zlib
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


DEFAULT_MAX_CHARS = 12000

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) "
    "AppleWebKit/537.36 "
    "Chrome/137 Safari/537.36"
)


class TextParser(HTMLParser):
    SKIP_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "nav",
        "footer",
        "header",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth > 0:
            return

        text = " ".join(data.split())

        if text:
            self.parts.append(text)

    def get_text(self):
        return " ".join(self.parts)


def clean_text(text):
    return " ".join((text or "").split())


def local_name(tag):
    if not tag:
        return ""

    return tag.rsplit("}", 1)[-1].lower()


def first_child_text(element, names):
    wanted = {name.lower() for name in names}

    for child in list(element):
        if local_name(child.tag) in wanted:
            return clean_text(child.text or "")

    return ""


def parse_rss(xml_bytes, max_chars):
    root = ET.fromstring(xml_bytes)

    channel = None

    if local_name(root.tag) == "rss":
        for child in list(root):
            if local_name(child.tag) == "channel":
                channel = child
                break

    elif local_name(root.tag) == "channel":
        channel = root

    items = []

    if channel is not None:

        channel_title = first_child_text(
            channel,
            ["title"]
        )

        channel_description = first_child_text(
            channel,
            ["description"]
        )

        for item in list(channel):

            if local_name(item.tag) != "item":
                continue

            title = first_child_text(
                item,
                ["title"]
            )

            link = first_child_text(
                item,
                ["link"]
            )

            published = first_child_text(
                item,
                [
                    "pubDate",
                    "published",
                    "updated",
                    "date"
                ]
            )

            description = first_child_text(
                item,
                [
                    "description",
                    "encoded",
                    "summary",
                    "content"
                ]
            )

            items.append({
                "title": title,
                "link": link,
                "published": published,
                "description": description,
            })

        feed_type = "rss"

        result = {
            "feed_type": feed_type,
            "title": channel_title,
            "description": channel_description,
            "items": items,
        }

    else:

        # 基础 Atom 支持
        feed_title = first_child_text(
            root,
            ["title"]
        )

        feed_description = first_child_text(
            root,
            [
                "subtitle",
                "description"
            ]
        )

        for entry in list(root):

            if local_name(entry.tag) != "entry":
                continue

            title = first_child_text(
                entry,
                ["title"]
            )

            published = first_child_text(
                entry,
                [
                    "published",
                    "updated"
                ]
            )

            description = first_child_text(
                entry,
                [
                    "summary",
                    "content"
                ]
            )

            link = ""

            for child in list(entry):

                if local_name(child.tag) != "link":
                    continue

                href = child.attrib.get(
                    "href",
                    ""
                )

                if href:
                    link = href
                    break

                link = clean_text(
                    child.text or ""
                )

            items.append({
                "title": title,
                "link": link,
                "published": published,
                "description": description,
            })

        feed_type = "atom"

        result = {
            "feed_type": feed_type,
            "title": feed_title,
            "description": feed_description,
            "items": items,
        }

    # 给模型准备的紧凑文本
    lines = []

    lines.append(
        f"Feed: {result['title']}"
    )

    if result.get("description"):
        lines.append(
            f"Description: {result['description']}"
        )

    lines.append(
        f"Items: {len(result['items'])}"
    )

    lines.append("")

    for index, item in enumerate(
        result["items"],
        1
    ):

        lines.append(
            f"[{index}] {item['title']}"
        )

        if item["published"]:
            lines.append(
                f"Published: {item['published']}"
            )

        if item["link"]:
            lines.append(
                f"Link: {item['link']}"
            )

        if item["description"]:
            lines.append(
                f"Summary: {item['description']}"
            )

        lines.append("")

    content = "\n".join(lines).strip()

    content = content[:max_chars]

    return {
        "success": True,
        "content_type": (
            "application/rss+xml"
            if feed_type == "rss"
            else "application/atom+xml"
        ),
        "feed_type": feed_type,
        "feed_title": result["title"],
        "item_count": len(result["items"]),
        "items": result["items"],
        "char_count": len(content),
        "content": content,
    }


def parse_html(raw_text, max_chars):
    parser = TextParser()

    parser.feed(raw_text)

    text = clean_text(
        parser.get_text()
    )

    return {
        "success": True,
        "content_type": "text/html",
        "char_count": len(text),
        "content": text[:max_chars],
    }


def web_open(
    url,
    max_chars=DEFAULT_MAX_CHARS,
    timeout=8
):

    if not isinstance(url, str):
        return {
            "success": False,
            "error": "URL 必须是字符串",
        }

    if not url.startswith(
        ("http://", "https://")
    ):
        return {
            "success": False,
            "error": (
                "URL 必须以 "
                "http:// 或 https:// 开头"
            ),
        }

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml,"
                "application/rss+xml,"
                "application/atom+xml,"
                "q=0.8,"
                "*/*;q=0.5"
            ),

            "Accept-Encoding": (
                "gzip, deflate"
            ),
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout
        ) as response:

            raw = response.read()

            content_encoding = (
                response.headers
                .get("Content-Encoding", "")
                .lower()
            )

            if "gzip" in content_encoding:
                raw = gzip.decompress(raw)

            elif "deflate" in content_encoding:
                raw = zlib.decompress(raw)

            final_url = response.geturl()

            content_type = (
                response.headers
                .get_content_type()
                .lower()
            )

            charset = (
                response.headers
                .get_content_charset()
                or "utf-8"
            )

        # RSS / Atom / XML
        if content_type in {
            "application/rss+xml",
            "application/atom+xml",
            "application/xml",
            "text/xml",
        }:

            try:

                result = parse_rss(
                    raw,
                    max_chars
                )

                result["url"] = url
                result["final_url"] = final_url

                return result

            except ET.ParseError as exc:

                return {
                    "success": False,
                    "url": url,
                    "final_url": final_url,
                    "content_type": content_type,
                    "error": (
                        f"XML 解析失败: {exc}"
                    ),
                }

        # 普通 HTML
        text = raw.decode(
            charset,
            errors="replace"
        )

        if (
            "html" in content_type
            or not content_type
        ):

            result = parse_html(
                text,
                max_chars
            )

        else:

            result = {
                "success": True,
                "content_type": content_type,
                "char_count": len(text),
                "content": text[:max_chars],
            }

        result["url"] = url
        result["final_url"] = final_url

        return result

    except urllib.error.HTTPError as exc:

        return {
            "success": False,
            "url": url,
            "status_code": exc.code,
            "error": (
                f"HTTP {exc.code}: {exc.reason}"
            ),
        }

    except urllib.error.URLError as exc:

        return {
            "success": False,
            "url": url,
            "error": (
                f"网络错误: {exc.reason}"
            ),
        }

    except TimeoutError:

        return {
            "success": False,
            "url": url,
            "error": "请求超时",
        }

    except Exception as exc:

        return {
            "success": False,
            "url": url,
            "error": (
                f"未知错误: {exc}"
            ),
        }


def main():

    if len(sys.argv) >= 2:
        url = sys.argv[1]
    else:
        url = input("URL：").strip()

    if len(sys.argv) >= 3:
        max_chars = int(sys.argv[2])
    else:
        max_chars = DEFAULT_MAX_CHARS

    result = web_open(
        url,
        max_chars=max_chars
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
