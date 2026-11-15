import csv
import io
import posixpath
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def sanitize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if "key" not in key.lower()} for row in rows]


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return sanitize(list(csv.DictReader(stream)))


def read_workbook(path: Path, sheet_name: str = "Deliveries") -> list[dict[str, Any]]:
    """Read cached cell values without executing workbook formulas or Power Query."""
    ns = {"m": MAIN_NS}
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(node.itertext())
                for node in ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            ]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall("m:sheets/m:sheet", ns)
        sheet = next((node for node in sheets if node.get("name") == sheet_name), None)
        if sheet is None:
            raise ValueError(f"Workbook has no {sheet_name!r} sheet.")
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(
            node.attrib["Target"]
            for node in relations
            if node.get("Id") == sheet.get(f"{{{REL_NS}}}id")
        )
        sheet_path = (
            target.lstrip("/") if target.startswith("/") else posixpath.normpath(f"xl/{target}")
        )
        root = ElementTree.fromstring(archive.read(sheet_path))
        matrix = []
        for row in root.findall("m:sheetData/m:row", ns):
            cells: dict[int, str] = {}
            for cell in row:
                letters = "".join(char for char in cell.attrib["r"] if char.isalpha())
                index = 0
                for char in letters:
                    index = index * 26 + ord(char.upper()) - ord("A") + 1
                value = cell.findtext("m:v", "", ns)
                if cell.get("t") == "s":
                    value = strings[int(value)]
                elif cell.get("t") == "inlineStr":
                    inline = cell.find("m:is", ns)
                    value = "".join(inline.itertext()) if inline is not None else ""
                cells[index - 1] = value
            if cells:
                matrix.append(cells)
        if len(matrix) < 2:
            raise ValueError("Workbook sheet has no delivery rows.")
        headers = matrix[0]
        rows = [
            {name: row.get(index, "") for index, name in headers.items() if name}
            for row in matrix[1:]
            if row.get(0)
        ]
        return sanitize(rows)


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise ValueError("No sample rows.")
    rows = sanitize(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")
