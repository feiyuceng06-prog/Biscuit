"""Check the actual OOXML and assemble side-by-side previews for the three frozen scenarios."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


def native(folder):
    with ZipFile(folder / "deck.pptx") as archive:

        def xml(name):
            return ET.fromstring(archive.read(name))

        slides, metrics = [], []
        for i in range(1, 4):
            slide = xml(f"ppt/slides/slide{i}.xml")
            shapes = slide.findall(".//{*}sp")
            text = ["".join(t.text or "" for t in shape.findall(".//{*}t")) for shape in shapes]
            notes = xml(f"ppt/notesSlides/notesSlide{i}.xml")
            slides.append(
                dict(
                    text=Counter(s for s in text if s),
                    notes=[t.text for t in notes.findall(".//{*}t")],
                    pictures=len(slide.findall(".//{*}pic")),
                    charts=len(slide.findall(".//{*}chart")),
                )
            )
            styles = [r for r in slide.findall(".//{*}rPr") if r.get("sz")]
            metrics.append(
                dict(
                    page=i,
                    editableTextBoxes=sum(bool(s) for s in text),
                    pictures=slides[-1]["pictures"],
                    charts=slides[-1]["charts"],
                    largestNativeTextPt=max(int(r.get("sz")) for r in styles) / 100,
                    typefaces=sorted({r.get("typeface") for r in slide.findall(".//{*}latin")}),
                )
            )
        data = [
            [v.text for v in xml(n).findall(".//{*}pt/{*}v")]
            for n in archive.namelist()
            if n.startswith("ppt/charts/chart") and n.endswith(".xml")
        ]
        assets = sorted(
            hashlib.sha256(archive.read(n)).hexdigest()
            for n in archive.namelist()
            if n.startswith("ppt/media/") and not n.endswith("/")
        )
        workbooks = []
        for book in sorted(n for n in archive.namelist() if n.startswith("ppt/embeddings/") and n.endswith(".xlsx")):
            with ZipFile(BytesIO(archive.read(book))) as workbook:
                workbooks.append({n: workbook.read(n) for n in workbook.namelist()
                                  if n.startswith("xl/worksheets/") or n == "xl/sharedStrings.xml"})
    return (slides, data, assets, workbooks), metrics


def audit(root):
    result = {}
    for case in ("product", "business", "technical"):
        records = {}
        native_content = {}
        sheet = Image.new("RGB", (960, 810), "white")
        for col, version in enumerate(("before", "after")):
            base = root / case / version
            native_content[version], metrics = native(base)
            report = json.loads((base / "review/report.json").read_text())
            assert hashlib.sha256((base / "deck.pptx").read_bytes()).hexdigest() == report["pptxSha256"]
            assert hashlib.sha256((base / "review/deck.pdf").read_bytes()).hexdigest() == report["pdfSha256"]
            assert len(report["pages"]) == len(metrics)
            for i, page in enumerate(report["pages"]):
                png = base / "review" / page["png"]
                assert hashlib.sha256(png.read_bytes()).hexdigest() == page["sha256"]
                with Image.open(png) as im:
                    sheet.paste(im.resize((480, 270), Image.Resampling.LANCZOS), (col * 480, i * 270))
            records[version] = dict(
                metrics=metrics,
                status=report["status"],
                critic=report["critic"],
                findings=[(i["slideId"], i["source"], i["kind"]) for i in report["issues"]],
            )
        assert native_content["before"] == native_content["after"], case + " editable content changed"
        sheet.save(root / case / "comparison.png")
        records["identicalContent"] = True
        result[case] = records
    (root / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


def direction_gallery(root, output):
    sheet = Image.new("RGB", (1440, 1080))
    for row, direction in enumerate(("editorial", "minimal", "corporate", "technology")):
        for col in range(3):
            with Image.open(root / "business" / direction / "review" / f"slide-{col + 1}.png") as image:
                sheet.paste(image.resize((480, 270), Image.Resampling.LANCZOS), (480 * col, 270 * row))
    sheet.save(output / "four-directions.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--gallery", type=Path, help="Directory containing the four fixed-content corporate brief renders")
    args = parser.parse_args()
    audit(args.evidence)
    if args.gallery:
        direction_gallery(args.gallery, args.evidence)
