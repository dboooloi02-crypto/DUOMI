import json

from web_search import web_search
from web_news import get_news_for_query
from web_open import web_open


WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索互联网获取最新或未知的信息。"
            "当用户询问可能过时的信息、最新消息、实时资料，"
            "或者 DUOMI 对某个事实没有足够把握时，可以使用此工具。"
            "普通闲聊、已有记忆足够回答的问题不需要搜索。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜索的互联网关键词或问题"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回多少条结果，范围 1 到 8",
                    "minimum": 1,
                    "maximum": 8
                }
            },
            "required": [
                "query"
            ]
        }
    }
}


WEB_NEWS_TOOL = {
    "type": "function",
    "function": {
        "name": "web_news",
        "description": (
            "获取特定主题的最新新闻。"
            "当用户明确询问某个主题的最新消息、新闻、最近更新时使用。"
            "当前工具优先读取已经验证过的官方 RSS 信息源，"
            "适合获取时间敏感的新闻列表。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户关于最新新闻或最近更新的问题"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回多少条新闻，范围 1 到 10",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": [
                "query"
            ]
        }
    }
}


WEB_OPEN_TOOL = {
    "type": "function",
    "function": {
        "name": "web_open",
        "description": (
            "打开一个互联网网页或 RSS/XML 信息源，"
            "读取其实际内容。"
            "当 web_search 找到相关网页后，"
            "需要查看页面具体内容、教程、文档、参数或原文时，"
            "应优先使用此工具深入阅读，"
            "不要只依赖搜索结果摘要。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "需要打开的完整 http:// 或 https:// URL"
                },
                "max_chars": {
                    "type": "integer",
                    "description": "最多读取多少字符，范围 1000 到 20000",
                    "minimum": 1000,
                    "maximum": 20000
                }
            },
            "required": [
                "url"
            ]
        }
    }
}


WEB_TOOLS = [
    WEB_SEARCH_TOOL,
    WEB_NEWS_TOOL,
    WEB_OPEN_TOOL
]


def execute_tool(tool_name, arguments):
    """
    执行 DUOMI 当前拥有的工具。
    """

    if tool_name == "web_search":

        query = arguments.get(
            "query",
            ""
        )

        max_results = arguments.get(
            "max_results",
            5
        )

        return web_search(
            query=query,
            max_results=max_results
        )

    if tool_name == "web_news":

        query = arguments.get(
            "query",
            ""
        )

        max_results = arguments.get(
            "max_results",
            5
        )

        return get_news_for_query(
            query=query,
            limit=max_results
        )

    if tool_name == "web_open":

        url = arguments.get(
            "url",
            ""
        )

        max_chars = arguments.get(
            "max_chars",
            12000
        )

        return web_open(
            url=url,
            max_chars=max_chars
        )

    return {
        "success": False,
        "error": f"未知工具：{tool_name}"
    }


def execute_tool_json(tool_name, arguments):

    result = execute_tool(
        tool_name,
        arguments
    )

    return json.dumps(
        result,
        ensure_ascii=False
    )
