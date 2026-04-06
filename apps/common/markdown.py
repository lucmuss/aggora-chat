from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import quote

import bleach
import markdown

from apps.accounts.mentions import MENTION_PATTERN, extract_mentioned_handles

ALLOWED_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "class"],
}


class MentionLinkifier(HTMLParser):
    def __init__(self, handles_to_urls: dict[str, str]):
        super().__init__(convert_charrefs=False)
        self.handles_to_urls = handles_to_urls
        self.parts: list[str] = []
        self.tag_stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tag_stack.append(tag)
        rendered_attrs = "".join(f' {name}="{escape(value or "", quote=True)}"' for name, value in attrs)
        self.parts.append(f"<{tag}{rendered_attrs}>")

    def handle_endtag(self, tag):
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        elif tag in self.tag_stack:
            self.tag_stack.remove(tag)
        self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        rendered_attrs = "".join(f' {name}="{escape(value or "", quote=True)}"' for name, value in attrs)
        self.parts.append(f"<{tag}{rendered_attrs} />")

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_data(self, data):
        if any(tag in {"a", "code", "pre"} for tag in self.tag_stack):
            self.parts.append(data)
            return

        def replace(match):
            handle = match.group(1).lower()
            url = self.handles_to_urls.get(handle)
            if not url:
                return match.group(0)
            return f'<a href="{escape(url, quote=True)}" class="mention-link">@{escape(handle)}</a>'

        self.parts.append(MENTION_PATTERN.sub(replace, data))

    def get_html(self) -> str:
        return "".join(self.parts)


def _linkify_mentions(html: str, markdown_text: str) -> str:
    handles = extract_mentioned_handles(markdown_text)
    if not handles:
        return html
    from apps.accounts.models import User

    existing_handles = set(User.objects.filter(handle__in=handles).values_list("handle", flat=True))
    if not existing_handles:
        return html
    handles_to_urls = {handle: f"/u/{quote(handle)}/" for handle in existing_handles}
    parser = MentionLinkifier(handles_to_urls)
    parser.feed(html)
    parser.close()
    return parser.get_html()


def render_markdown(markdown_text: str) -> str:
    raw_html = markdown.markdown(
        markdown_text or "",
        extensions=["fenced_code", "tables", "nl2br"],
    )
    sanitized_html = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    return _linkify_mentions(sanitized_html, markdown_text or "")
