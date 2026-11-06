"""Print every AcroForm field of a PDF as JSON.

Run: `make dump-fields PDF=seed/forms/pdf/pva_pflegegeld.pdf`

Each entry: name, type, pages (1-based), value, label (nearby text on the
page), max_len (if set) and, for checkboxes and radio buttons, options (export
state plus the text next to that box). Labels need PyMuPDF; without it they
stay empty.
Use the output to build `seed/forms/field_maps/<form_id>.json`.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.generic import DictionaryObject, StreamObject

FIELD_TYPES = {"/Tx": "text", "/Btn": "button", "/Ch": "choice", "/Sig": "signature"}
BUTTON_TYPES = {"checkbox", "radio"}
LABEL_MAX_CHARS = 160
WORD_GAP = 15  # points; a wider gap ends an option label


def qualified_name(annot: DictionaryObject) -> str:
    """Join the /T parts of a widget and its parents: `parent.child`."""
    parts: list[str] = []
    node: DictionaryObject | None = annot
    while node is not None:
        if "/T" in node:
            parts.append(str(node["/T"]))
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return ".".join(reversed(parts))


def inherited(annot: DictionaryObject, key: str) -> Any:
    node: DictionaryObject | None = annot
    while node is not None:
        if key in node:
            return node[key]
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def on_states(annot: DictionaryObject) -> list[str]:
    """Export states of one checkbox or radio widget, without /Off."""
    appearance = annot.get("/AP")
    if appearance is None:
        return []
    normal = appearance.get_object().get("/N")
    if normal is None:
        return []
    normal = normal.get_object()
    if isinstance(normal, StreamObject) or not isinstance(normal, DictionaryObject):
        return []
    return [str(state) for state in normal if str(state) != "/Off"]


def field_type(annot: DictionaryObject) -> str:
    kind = FIELD_TYPES.get(str(inherited(annot, "/FT")), "unknown")
    if kind != "button":
        return kind
    flags = int(inherited(annot, "/Ff") or 0)
    if flags & (1 << 16):
        return "pushbutton"
    if flags & (1 << 15):
        return "radio"
    return "checkbox"


def read_fields(pdf_path: Path) -> list[dict[str, Any]]:
    """Return one entry per field in page order. Widgets of a field merge."""
    reader = PdfReader(pdf_path)
    fields: dict[str, dict[str, Any]] = {}
    for page_number, page in enumerate(reader.pages, start=1):
        for ref in page.get("/Annots") or []:
            annot = ref.get_object()
            if annot.get("/Subtype") != "/Widget":
                continue
            name = qualified_name(annot)
            if not name:
                continue
            kind = field_type(annot)
            value = inherited(annot, "/V")
            entry = fields.setdefault(
                name,
                {
                    "name": name,
                    "type": kind,
                    "pages": [],
                    "value": None if value is None else str(value),
                    "label": "",
                },
            )
            max_len = inherited(annot, "/MaxLen")
            if max_len is not None:
                entry["max_len"] = int(max_len)
            if page_number not in entry["pages"]:
                entry["pages"].append(page_number)
            if kind in BUTTON_TYPES:
                options = entry.setdefault("options", [])
                known = {option["state"] for option in options}
                for state in on_states(annot):
                    if state not in known:
                        options.append({"state": state, "label": ""})
    return list(fields.values())


def add_labels(pdf_path: Path, fields: list[dict[str, Any]]) -> None:
    """Fill `label` and option labels from the words around each widget."""
    try:
        import pymupdf
    except ImportError:
        return
    by_name = {field["name"]: field for field in fields}
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            words = page.get_text("words")
            for widget in page.widgets() or []:
                field = by_name.get(widget.field_name)
                if field is None:
                    continue
                if not field["label"]:
                    field["label"] = _label_left_or_above(words, widget.rect)
                options = {o["state"]: o for o in field.get("options", [])}
                states = (widget.button_states() or {}).get("normal") or []
                for state in states:
                    option = options.get(f"/{state}")
                    if option is not None and not option["label"]:
                        option["label"] = _label_right(words, widget.rect)


def _label_left_or_above(words: list[tuple], rect: Any) -> str:
    """Words on the same line left of the field, else the line above it."""
    mid_y = (rect.y0 + rect.y1) / 2
    left = [
        w for w in words
        if w[2] <= rect.x0 + 2 and w[1] <= mid_y <= w[3] and rect.x0 - w[2] < 260
    ]
    if left:
        return _join(left)
    above = [
        w for w in words
        if w[3] <= rect.y0 + 2
        and rect.y0 - w[3] < 18
        and w[2] >= rect.x0 - 4
        and w[0] <= rect.x1 + 4
    ]
    if not above:
        return ""
    bottom = max(w[3] for w in above)
    return _join([w for w in above if bottom - w[3] < 4])


def _label_right(words: list[tuple], rect: Any) -> str:
    """Words right of a box on the same line, up to the first wide gap."""
    mid_y = (rect.y0 + rect.y1) / 2
    right = sorted(
        (w for w in words if w[0] >= rect.x1 - 2 and w[1] <= mid_y <= w[3]),
        key=lambda w: w[0],
    )
    picked: list[tuple] = []
    edge = rect.x1
    for word in right:
        if word[0] - edge > WORD_GAP:
            break
        picked.append(word)
        edge = word[2]
    return _join(picked)


def _join(words: list[tuple]) -> str:
    ordered = sorted(words, key=lambda w: (round(w[1]), w[0]))
    return " ".join(w[4] for w in ordered)[-LABEL_MAX_CHARS:]


def dump(pdf_path: Path) -> list[dict[str, Any]]:
    fields = read_fields(pdf_path)
    add_labels(pdf_path, fields)
    return fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path, help="path to an AcroForm PDF")
    args = parser.parse_args(argv)
    if not args.pdf.is_file():
        print(f"File not found: {args.pdf}", file=sys.stderr)
        return 1
    json.dump(dump(args.pdf), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
