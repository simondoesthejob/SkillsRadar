"""Text clean-up: remove personal contact details from posting text."""

from __future__ import annotations

import re
from html.parser import HTMLParser

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

# Phone numbers: international (+44 20 7946 0958), UK national (020 7946 0958, 07700 900123) and
# US style (415-555-0132). Deliberately narrow so salary ranges ("45000-55000", "£45,000") and
# year ranges ("2019-2024") are left alone.
PHONE = re.compile(
    r"""
    (?<![\w£$€.,/])
    (?:
        \+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}
      | 0\d{2,4}(?:[\s-]?\d{3,4}){2}
      | \(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}
    )
    (?!\w)
    """,
    re.VERBOSE,
)

EMAIL_PLACEHOLDER = "[email removed]"
PHONE_PLACEHOLDER = "[phone removed]"


def strip_pii(text: str | None) -> tuple[str | None, dict[str, int]]:
    """Replace emails and phone numbers. Returns the cleaned text and how many of each."""
    if not text:
        return text, {"emails": 0, "phones": 0}
    text, emails = EMAIL.subn(EMAIL_PLACEHOLDER, text)
    text, phones = PHONE.subn(PHONE_PLACEHOLDER, text)
    return text, {"emails": emails, "phones": phones}


_BLOCK_TAGS = {
    "p", "div", "br", "ul", "ol", "tr", "table", "section", "h1", "h2", "h3", "h4", "h5", "h6",
}  # fmt: skip


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    """Plain text from an HTML job description: tags dropped, list items kept as "- " lines."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines).replace("\xa0", " ")).strip()
