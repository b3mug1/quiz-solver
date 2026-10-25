"""Used for controlled HTML fixtures and optional server-side extraction."""

def parse_questions(html: str) -> list[dict]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return _standard_parser(html)
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for fieldset in soup.select("fieldset"):
        legend = fieldset.find("legend")
        inputs = fieldset.select('input[type="radio"], input[type="checkbox"]')
        if not legend or len(inputs) < 2:
            continue
        options = []
        for index, item in enumerate(inputs):
            label = item.find_parent("label") or fieldset.find("label", attrs={"for": item.get("id", "")})
            if label:
                options.append({"id": item.get("value") or str(index), "text": label.get_text(" ", strip=True)})
        if len(options) >= 2:
            result.append({"text": legend.get_text(" ", strip=True), "options": options,
                           "question_type": "multiple_choice" if inputs[0].get("type") == "checkbox" else "single_choice"})
    return result


def _standard_parser(html: str) -> list[dict]:
    """Small offline fallback for semantic fieldsets when bs4 is unavailable."""
    from html.parser import HTMLParser

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.result = []
            self.current = None
            self.capture = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "fieldset":
                self.current = {"text": "", "options": [], "question_type": "single_choice"}
            elif self.current is not None and tag in ("legend", "label"):
                self.capture = tag
                if tag == "label":
                    self.current["options"].append({"id": "", "text": ""})
            elif self.current is not None and tag == "input" and self.current["options"]:
                self.current["options"][-1]["id"] = attrs.get("value", str(len(self.current["options"]) - 1))
                if attrs.get("type") == "checkbox":
                    self.current["question_type"] = "multiple_choice"

        def handle_data(self, data):
            if self.current is not None and self.capture == "legend":
                self.current["text"] += data
            elif self.current is not None and self.capture == "label" and self.current["options"]:
                self.current["options"][-1]["text"] += data

        def handle_endtag(self, tag):
            if tag == self.capture:
                self.capture = None
            if tag == "fieldset" and self.current is not None:
                if self.current["text"].strip() and len(self.current["options"]) >= 2:
                    self.current["text"] = self.current["text"].strip()
                    for option in self.current["options"]:
                        option["text"] = option["text"].strip()
                    self.result.append(self.current)
                self.current = None

    parser = Parser()
    parser.feed(html)
    return parser.result
