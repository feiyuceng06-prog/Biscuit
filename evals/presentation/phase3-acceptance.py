"""Audit the saved Visual Planner acceptance evidence using standard OOXML and Poppler."""

import hashlib
import itertools
import json
import posixpath
import subprocess
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2] / "docs/presentation/phase-3"
DEST = ROOT / "acceptance"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linked_part(package, part, relationship):
    folder, filename = posixpath.split(part)
    relations = ET.fromstring(
        package.read(posixpath.join(folder, "_rels", filename + ".rels"))
    )
    target = next(r.get("Target") for r in relations if r.get("Id") == relationship)
    return posixpath.normpath(posixpath.join(folder, target)).lstrip("/")


def architecture_retry():
    folder = ROOT / "evidence/architecture/phase3"
    review = folder / "review"
    report = json.loads((review / "report.json").read_text())
    assert sha(folder / "deck.pptx") == report["pptxSha256"]
    assert sha(review / "deck.pdf") == report["pdfSha256"]
    retry = json.loads((review / "critic-retry.json").read_text())
    checked = set(report["critic"]["checkedSlides"])
    pages = {p["slideId"]: p for p in report["pages"]}
    assert checked == {"architecture-1"} and len(retry) == 3
    paths = []
    for r in retry:
        page = pages[r["slideId"]]
        assert r["sha256"] == page["sha256"] == sha(review / page["png"])
        assert r["status"] == "checked" and r["checkedSlides"] == [r["slideId"]]
        assert (
            r["modelAlias"] == report["critic"]["modelAlias"]
            and r["slideId"] not in checked
        )
        checked.add(r["slideId"])
    assert checked == set(pages)
    for slide, p in pages.items():
        assert sha(review / p["png"]) == p["sha256"]
        paths.append(
            {
                "slide": slide,
                "sha256": p["sha256"],
                "review": "initial" if slide.endswith("-1") else "retry",
            }
        )
    return {
        "pptx": report["pptxSha256"],
        "pdf": report["pdfSha256"],
        "manifest": sha(folder / "manifest.json"),
        "initialError": report["critic"]["errorType"],
        "model": report["critic"]["modelAlias"],
        "pages": paths,
    }


def long_labels(folder):
    review = folder / "review"
    manifest = json.loads((folder / "manifest.json").read_text())
    chart = next(
        obj for obj in manifest["slides"][0]["objects"] if obj.get("wrappedCategories")
    )
    pdf = ET.fromstring(
        subprocess.check_output(
            ["pdftotext", "-bbox-layout", str(review / "deck.pdf"), "-"]
        )
    )
    words = list(pdf.iterfind(".//{*}word"))
    report = json.loads((review / "report.json").read_text())
    assert sha(folder / "deck.pptx") == report["pptxSha256"]
    assert sha(review / "slide-1.png") == report["pages"][0]["sha256"]
    with ZipFile(folder / "deck.pptx") as deck:
        slide_part = "ppt/slides/slide1.xml"
        slide = ET.fromstring(deck.read(slide_part))
        chart_part = linked_part(
            deck, slide_part, slide.find(".//{*}chart").attrib[REL + "id"]
        )
        graph = ET.fromstring(deck.read(chart_part))
        book_part = linked_part(
            deck, chart_part, graph.find(".//{*}externalData").attrib[REL + "id"]
        )
        with ZipFile(BytesIO(deck.read(book_part))) as book:
            ws = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
            shared = [
                s.findtext("{*}t")
                for s in ET.fromstring(book.read("xl/sharedStrings.xml"))
            ]
        rows = []
        for idx, item in enumerate(chart["items"]):
            label, number = item["label"], item["value"]
            shape = next(
                sp
                for sp in slide.findall(".//{*}sp")
                if "".join(sp.itertext()).strip() == label
                or "".join(t.text or "" for t in sp.findall(".//{*}t")) == label
            )
            assert shape.find(".//{*}fld") is None
            xfrm = shape.find(".//{*}xfrm")
            top = int(xfrm.find("{*}off").get("y")) / 12700
            bottom = top + int(xfrm.find("{*}ext").get("cy")) / 12700
            word = next(w for w in words if w.text == str(number))
            center = (float(word.get("yMin")) + float(word.get("yMax"))) / 2
            assert top <= center <= bottom, (label, top, center, bottom)
            category = graph.find(f'.//{{*}}cat//{{*}}pt[@idx="{idx}"]/{{*}}v').text
            cache = float(graph.find(f'.//{{*}}val//{{*}}pt[@idx="{idx}"]/{{*}}v').text)
            cell = ws.find(f'.//{{*}}c[@r="B{idx + 2}"]')
            value = cell.findtext("{*}v")
            assert (
                label
                == category
                == shared[int(ws.findtext(f'.//{{*}}c[@r="A{idx + 2}"]/{{*}}v'))]
            )
            assert cache == number
            if folder.name == "original" and number == 0:
                assert not value
            else:
                assert cell.get("t", "n") == "n" and float(value) == number
            rows.append(
                {
                    "row": idx + 2,
                    "category": category,
                    "cache": cache,
                    "worksheet": value,
                    "independentLabelBoundsY": [round(top, 2), round(bottom, 2)],
                    "renderedValueCenterY": round(center, 2),
                }
            )
    return {
        "pptx": report["pptxSha256"],
        "png": report["pages"][0]["sha256"],
        "rows": rows,
    }


def photography(folder):
    from base64 import b64decode

    source = json.loads((folder / "source.deck.json").read_text())
    manifest = json.loads((folder / "manifest.json").read_text())
    report = json.loads((folder / "review/report.json").read_text())
    assert sha(folder / "deck.pptx") == report["pptxSha256"]
    assert sha(folder / "review/deck.pdf") == report["pdfSha256"]
    sources = {
        str(row["objectID"]): row
        for row in json.loads((DEST / "sources.json").read_text())
    }
    assert (
        source["design"]["version"] == 2
        and source["design"]["direction"] == "photography"
    )
    summaries = []
    with ZipFile(folder / "deck.pptx") as package:
        for n, s in enumerate(source["slides"], 1):
            part = f"ppt/slides/slide{n}.xml"
            page = ET.fromstring(package.read(part))
            notes = ET.fromstring(package.read(f"ppt/notesSlides/notesSlide{n}.xml"))
            assert s["notes"] in [e.text for e in notes.findall(".//{*}t")]
            shapes = page.findall(".//{*}sp")
            texts = {
                "".join(t.text or "" for t in sp.findall(".//{*}t")): sp
                for sp in shapes
            }
            for value in [
                s["title"],
                *(i[k] for i in s["items"] for k in ("label", "text") if i[k]),
            ]:
                assert value in texts, value
            png = report["pages"][n - 1]
            assert (
                png["slideId"] == s["id"]
                and sha(folder / "review" / png["png"]) == png["sha256"]
            )
            font = texts[s["title"]].find(".//{*}rPr")
            assert (
                font.get("i") == "1"
                and font.find("{*}latin").get("typeface") == "Liberation Serif"
            )
            fonts = subprocess.check_output(
                [
                    "pdffonts",
                    "-f",
                    str(n),
                    "-l",
                    str(n),
                    str(folder / "review/deck.pdf"),
                ],
                text=True,
            )
            assert "LiberationSerif-Italic" in fonts
            objects = manifest["slides"][n - 1]["objects"]
            pictures = page.findall(".//{*}pic")
            photo_shapes = [obj for obj in objects if obj["type"] == "image"]
            assert len(pictures) == len(photo_shapes) == len(s["photos"])
            images = []
            for photo, shape, obj in zip(s["photos"], pictures, photo_shapes):
                catalogue = sources[Path(photo["name"]).stem]
                assert (
                    catalogue["isPublicDomain"] and catalogue["objectURL"] in s["notes"]
                )
                asset = linked_part(
                    package, part, shape.find(".//{*}blip").attrib[REL + "embed"]
                )
                assert package.read(asset) == b64decode(photo["data"].partition(",")[2])
                assert shape.find(".//{*}cNvPr").get("name") == photo["name"]
                xf = shape.find(".//{*}xfrm")
                numbers = [xf.find("{*}off").get(k) for k in ["x", "y"]] + [
                    xf.find("{*}ext").get(k) for k in ["cx", "cy"]
                ]
                box = [int(v) / 12700 for v in numbers]
                assert all(abs(v - obj[key]) < 0.001 for v, key in zip(box, "xywh"))
                crop = shape.find(".//{*}srcRect")
                if "crop" in obj:
                    rect = obj["crop"]
                    for key, val in zip(
                        ("l", "t", "r", "b"),
                        [
                            rect["x"],
                            rect["y"],
                            1 - rect["x"] - rect["w"],
                            1 - rect["y"] - rect["h"],
                        ],
                    ):
                        assert abs(int(crop.get(key)) / 100000 - val) < 0.00002
                else:
                    assert crop is None
                images.append(
                    {
                        "objectID": catalogue["objectID"],
                        "xywhPt": box,
                        "nativeCrop": crop.attrib if crop is not None else {},
                    }
                )
            if folder.name == "portrait":
                assert len(images) == 5 and len([t for t in texts if t]) == 3
                assert [round(p["xywhPt"][2]) for p in images] == [
                    86,
                    168,
                    236,
                    168,
                    86,
                ]
                for a, b in itertools.pairwise(images):
                    assert (
                        abs(b["xywhPt"][0] - a["xywhPt"][0] - a["xywhPt"][2] - 7)
                        < 0.001
                    )
            summaries.append(
                {
                    "page": n,
                    "variant": source["design"]["slidePlans"][n - 1]["variant"],
                    "imageObjects": images,
                    "nativeTitlePt": int(font.get("sz")) / 100,
                    "renderedTitleFont": "LiberationSerif-Italic",
                    "png": png["sha256"],
                }
            )
    return {
        "pptx": report["pptxSha256"],
        "pdf": report["pdfSha256"],
        "slides": summaries,
    }


if __name__ == "__main__":
    results = {v: long_labels(DEST / "chart-labels" / v) for v in ["original", "fixed"]}
    assert results["original"]["png"] == results["fixed"]["png"]
    print(
        json.dumps(
            {
                "architecture": architecture_retry(),
                "labels": results,
                "samples": {c: photography(DEST / c) for c in ["portrait", "sea"]},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
