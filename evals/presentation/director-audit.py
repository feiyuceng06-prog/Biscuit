"""Check exported Office contents and assemble fixed-input visual comparisons."""

import argparse
import hashlib
import json
import posixpath
import xml.etree.ElementTree as ET
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops


def native(folder):
    with ZipFile(folder / "deck.pptx") as archive:

        def xml(name):
            return ET.fromstring(archive.read(name))

        slides, metrics = [], []
        count = len(xml("ppt/presentation.xml").findall(".//{*}sldIdLst/{*}sldId"))
        for i in range(1, count + 1):
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


def source_charts(folder, slide_count):
    result = {}
    with ZipFile(folder / "deck.pptx") as archive:
        for page in range(1, slide_count + 1):
            slide = ET.fromstring(archive.read(f"ppt/slides/slide{page}.xml"))
            chart = slide.find(".//{*}chart")
            if chart is None:
                continue
            rels = ET.fromstring(archive.read(f"ppt/slides/_rels/slide{page}.xml.rels"))
            rid = chart.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = next(rel.get("Target") for rel in rels if rel.get("Id") == rid)
            name = posixpath.normpath(posixpath.join("ppt/slides", target)).lstrip("/")
            area = ET.fromstring(archive.read(name)).find(".//{*}plotArea")
            plot = next(child for child in area if child.tag.endswith("Chart"))
            encoding = plot.tag.split("}")[-1]
            if encoding == "barChart":
                encoding = plot.find("{*}barDir").get("val")
            series = plot.findall("{*}ser")
            assert len(series) == 1, "Fixtures contain a single numeric series per chart"
            result[page] = (
                encoding,
                [v.text for v in series[0].findall("{*}cat//{*}pt/{*}v")],
                [float(v.text) for v in series[0].findall("{*}val//{*}pt/{*}v")],
            )
    return result


def planner_audit(root):
    fixtures = json.loads(Path(__file__).with_name("planner-cases.json").read_text())
    results = {}
    for case in fixtures:
        directory = root / case["id"]
        count = len(case["slides"])
        sheet = Image.new("RGB", (960, 270 * count))
        pages = []
        snapshots = {}
        for col, version in enumerate(("phase2", "phase3")):
            base = directory / version
            snapshot, metrics = native(base)
            charts = source_charts(base, count)
            snapshots[version] = snapshot
            design = json.loads((base / "design.json").read_text())
            manifest = json.loads((base / "manifest.json").read_text())
            review_dir = base / "review"
            report = json.loads((review_dir / "report.json").read_text())
            retry_file = review_dir / "critic-retry.json"
            retries = {r["slideId"]: r for r in json.loads(retry_file.read_text())} if retry_file.exists() else {}
            assert retries.keys() <= {p["slideId"] for p in report["pages"]}
            assert design["version"] == col + 1
            assert hashlib.sha256((base / "deck.pptx").read_bytes()).hexdigest() == report["pptxSha256"]
            assert hashlib.sha256((review_dir / "deck.pdf").read_bytes()).hexdigest() == report["pdfSha256"]
            assert len(report["pages"]) == len(metrics) == len(manifest["slides"]) == count
            if col == 0:
                tokens = design["tokens"]
            else:
                assert tokens == design["tokens"], "The A/B must use identical global tokens"
                assert len(design["slidePlans"]) == count
            for i, (page, src, native_page) in enumerate(zip(report["pages"], case["slides"], snapshot[0])):
                layout, title, items, *detail = src
                source_text = [title, *(item[1] for item in items if item[1])]
                if layout == "chart":
                    source_text.append(detail[0])
                    _, categories, values = charts[i + 1]
                    assert categories == [item[0] for item in items], (case["id"], version, i + 1)
                    assert values == [item[2] for item in items], (case["id"], version, i + 1)
                else:
                    source_text.extend(item[0] for item in items if item[0])
                for value in source_text:
                    assert value in native_page["text"], (case["id"], version, i + 1, value)
                assert native_page["pictures"] == int(detail == ["photo"])
                assert native_page["charts"] == int(layout == "chart")
                expected_note = "设计对照样例。" + title + "。材料来自固定输入 " + case["id"] + "。"
                assert expected_note in "".join(native_page["notes"])
                path = review_dir / page["png"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == page["sha256"]
                with Image.open(path) as im:
                    sheet.paste(im.resize((480, 270), Image.Resampling.LANCZOS), (col * 480, i * 270))
                    if col:
                        with Image.open(directory / "phase2" / "review" / page["png"]) as old:
                            diff = ImageChops.difference(im.convert("RGB"), old.convert("RGB"))
                            bands = diff.split()
                            maximum = ImageChops.lighter(ImageChops.lighter(bands[0], bands[1]), bands[2])
                            changed = sum(maximum.histogram()[19:]) / (im.width * im.height)
                findings = [f for f in report["issues"] if f["slideId"] == page["slideId"]]
                checked = page["slideId"] in report["critic"].get("checkedSlides", [])
                replay = retries.get(page["slideId"])
                if replay:
                    assert not checked and replay["sha256"] == page["sha256"]
                    assert replay["modelAlias"] == report["critic"]["modelAlias"]
                    checked = replay["status"] == "checked" and replay["checkedSlides"] == [page["slideId"]]
                    if checked:
                        findings.extend(replay["issues"])
                row = {
                    "titlePt": next(o["size"] for o in manifest["slides"][i]["objects"] if o.get("field") == "title"),
                    "editableTextBoxes": metrics[i]["editableTextBoxes"],
                    "nativeChart": charts[i + 1][0] if i + 1 in charts else None,
                    "deterministic": [f["kind"] for f in findings if f["source"] == "deterministic"],
                    "vision": [f["kind"] for f in findings if f["source"] == "vision-model"],
                    "visionChecked": checked,
                    "visionReplay": bool(replay),
                }
                if col == 0:
                    pages.append({"slideId": page["slideId"], "sourceLayout": layout, version: row})
                else:
                    plan = design["slidePlans"][i]
                    assert page["slideId"] == plan["slideId"] and plan["selectionReason"]
                    pages[i].update(phase3=row, family=plan["layout"], variant=plan["variant"],
                                    changedPixelFraction=round(changed, 4))
        old, new = snapshots["phase2"], snapshots["phase3"]
        assert old[1:] == new[1:], "Chart caches, embedded images or editable workbook data changed"
        for a, b in zip(old[0], new[0]):
            assert a["notes"] == b["notes"]
        sheet.save(directory / "comparison.png")
        results[case["id"]] = pages
    (root / "audit.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")


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
    parser.add_argument("--planner", action="store_true", help="Audit the Phase 2/3 fixed-input pairs")
    args = parser.parse_args()
    if args.planner:
        planner_audit(args.evidence)
    else:
        audit(args.evidence)
    if args.gallery:
        direction_gallery(args.gallery, args.evidence)
