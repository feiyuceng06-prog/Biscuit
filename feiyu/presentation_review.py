"""Inspect native Biscuit exports with Impress, Poppler and Pillow, without editing them."""

import hashlib
import io
import json
import os
import posixpath
import shutil
import subprocess
import tempfile
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    return subprocess.run(args, capture_output=True, check=True, timeout=90)


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", value).split())


def luminance(rgb):
    channels = [int(rgb[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))


def issue(page, element, kind, evidence, suggestion, severity="blocker"):
    return {
        "issueId": f"{page}:{element or 'page'}:{kind}",
        "slideId": page,
        "elementIds": [element] if element else [],
        "kind": kind,
        "severity": severity,
        "confidence": 1,
        "evidence": evidence,
        "suggestedChange": suggestion,
        "source": "deterministic",
    }


def word_center(bounds):
    x = (bounds[0] + bounds[2]) / 2
    y = (bounds[1] + bounds[3]) / 2
    return x, y, x, y


def contains(outer, inner, tolerance=0):
    return (
        outer[0] - tolerance <= inner[0]
        and outer[1] - tolerance <= inner[1]
        and outer[2] + tolerance >= inner[2]
        and outer[3] + tolerance >= inner[3]
    )


def matching_words(words, text, bounds):
    if not text:
        return []
    x, y, right, bottom = bounds
    for start, (_, (left, top, word_right, word_bottom)) in enumerate(words):
        if word_right < x - 2 or left > right + 2 or word_bottom < y - 2 or top > bottom + 2:
            continue
        remaining = text
        for stop in range(start, len(words)):
            value = normalized(words[stop][0])
            if not remaining.startswith(value):
                break
            remaining = remaining[len(value) :]
            if not remaining:
                return words[start : stop + 1]
    return []


def inspect_page(slide, words, native, archive, relationships, image):
    page = slide["slideId"]
    issues, layers, text_frames = [], [], []
    shapes = [s for s in native.find(".//{*}spTree") if s.tag.split("}")[-1] in ("sp", "pic", "graphicFrame")]
    if len(shapes) != len(slide["objects"]):
        issues.append(
            issue(
                page,
                None,
                "object-count",
                f"{len(shapes)} PPTX objects, expected {len(slide['objects'])}",
                "Re-export the complete page.",
            )
        )
    if image.convert("RGB").getcolors(1) is not None:
        issues.append(
            issue(page, None, "blank", "The raster has one unique colour.", "Inspect slide visibility.")
        )
    for expected, shape in zip(slide["objects"], shapes):
        element = expected["id"]

        def add(kind, evidence, suggestion, severity="blocker", *, element=element):
            issues.append(issue(page, element, kind, evidence, suggestion, severity))

        transform = shape.find(".//{*}xfrm")
        offset, extent = transform.find("{*}off"), transform.find("{*}ext")
        x, y, w, h = [
            int(node.get(key)) / 12700
            for node, key in [(offset, "x"), (offset, "y"), (extent, "cx"), (extent, "cy")]
        ]
        bounds = (x, y, x + w, y + h)
        if not contains((0, 0, 960, 540), bounds, 0.05):
            add(
                "out-of-bounds",
                f"PPTX box {bounds} pt exceeds 960 × 540 pt.",
                "Move the object inside the slide.",
            )
        kind = expected["type"]
        if kind == "rect":
            fill = shape.find(".//{*}spPr/{*}solidFill/{*}srgbClr")
            layers.append((bounds, fill.get("val") if fill is not None else None))
        elif kind == "image":
            layers.append((bounds, None))
            visible_w = visible_h = 1
            if expected.get("photoId"):
                source_rect = shape.find(".//{*}srcRect")
                crop = [int(source_rect.get(axis, "0")) / 100000 if source_rect is not None else 0
                        for axis in ("l", "t", "r", "b")]
                visible_w, visible_h = 1 - crop[0] - crop[2], 1 - crop[1] - crop[3]
                target = expected.get("crop", {"x": 0, "y": 0, "w": 1, "h": 1})
                intended = [target["x"], target["y"], 1 - target["x"] - target["w"],
                            1 - target["y"] - target["h"]]
                if any(abs(a - b) > 0.00002 for a, b in zip(crop, intended)):
                    add("image-crop", f"PPTX crop {crop} differs from {intended}.",
                        "Re-export to apply the planned photo crop.")
                if any(abs(a - expected[key]) > 0.05 for a, key in zip((x, y, w, h), ("x", "y", "w", "h"))):
                    add("image-position", f"PPTX photo box {bounds} differs from the planned box.",
                        "Re-export to apply the planned photo position.")
            blip = shape.find(".//{*}blip")
            rid = (
                next((v for k, v in blip.attrib.items() if k.endswith("}embed")), None)
                if blip is not None
                else None
            )
            target = relationships.get(rid, "")
            try:
                with Image.open(
                    io.BytesIO(
                        archive.read(posixpath.normpath(posixpath.join("ppt/slides", target)).lstrip("/"))
                    )
                ) as asset:
                    asset.verify()
                    pixel_w, pixel_h = asset.width * visible_w, asset.height * visible_h
                    if pixel_w < w / 2 or pixel_h < h / 2:
                        add(
                            "low-resolution",
                            f"{pixel_w:g} × {pixel_h:g} visible px in {w:g} × {h:g} pt.",
                            "Supply a larger source image.",
                            "major",
                        )
            except (KeyError, ValueError, OSError, SyntaxError):
                add("missing-image", "Embedded image cannot be decoded.", "Reattach the original image.")
        elif kind in ("text", "chart"):
            # Match word centres, since Poppler ascent/descent includes space outside the ink.
            local = [(v, b) for v, b in words if contains(bounds, word_center(b), 2)]
            if kind == "chart":
                content = normalized("".join(v for v, _ in local))
                ref = shape.find(".//{*}chart")
                rid = next(iter(ref.attrib.values()), "") if ref is not None else ""
                target = posixpath.normpath(posixpath.join("ppt/slides", relationships.get(rid, ""))).lstrip(
                    "/"
                )
                try:
                    chart = ET.fromstring(archive.read(target))
                    cats = [n.text or "" for n in chart.findall(".//{*}ser/{*}cat//{*}pt/{*}v")]
                    values = [float(n.text) for n in chart.findall(".//{*}ser/{*}val//{*}pt/{*}v")]
                    valid = cats == [item["label"] for item in expected["items"]] and values == [
                        item["value"] for item in expected["items"]
                    ]
                except (KeyError, ValueError, ET.ParseError):
                    valid = False
                if not valid:
                    add(
                        "chart-data",
                        "Native chart labels or values differ from the source.",
                        "Restore the original categories and numeric values.",
                    )
                labels = [str(item[key]) for item in expected["items"] for key in ("label", "value")]
                if any(normalized(v) not in content for v in labels):
                    add(
                        "chart-label",
                        "Expected category or value missing from rendered chart region.",
                        "Verify labels and units against the source.",
                        "major",
                    )
                continue
            for other, b in text_frames:
                overlap_w = min(bounds[2], b[2]) - max(x, b[0])
                overlap_h = min(bounds[3], b[3]) - max(y, b[1])
                shared_words = any(contains(b, word_center(wb)) for _, wb in local)
                if overlap_w > 3 and overlap_h > 3 and shared_words:
                    add(
                        "overlap",
                        f"Text frame intersects {other} by {overlap_w:.1f} × {overlap_h:.1f} pt.",
                        "Inspect the intersecting text frames in the preview.",
                        "major",
                    )
                    break
            text_frames.append((element, bounds))
            text = normalized(expected["value"])
            stored = normalized("".join(n.text or "" for n in shape.findall(".//{*}t")))
            if stored != text:
                add(
                    "missing-text",
                    "Native text differs from the source composition.",
                    "Restore the original characters before export.",
                )
            # An unwrapped word may start inside the frame with its centre well outside it.
            rendered = matching_words(local, stored, bounds) or matching_words(words, stored, bounds)
            if not rendered:
                # Poppler may emit aligned CJK words column-first within one text box.
                rows = sorted(local, key=lambda word: (round(word[1][1], 1), word[1][0]))
                rendered = matching_words(rows, stored, bounds)
            content = "".join(v for v, _ in (rendered or local))
            bad_glyph = "\ufffd" in content
            if stored and not rendered and not bad_glyph:
                add(
                    "clipping",
                    "PDF words associated with the PPTX text box do not reconstruct the native text.",
                    "Check the PNG for cropped or missing characters and verify the extraction order.",
                    "major",
                )
            if bad_glyph:
                add(
                    "missing-glyph",
                    "PDF text contains a Unicode replacement character.",
                    "Check the original character and font coverage.",
                )
            excess = 0
            for _, (left, top, right, bottom) in rendered:
                mid_y = (top + bottom) / 2
                excess = max(excess, x - left, right - (x + w), y - mid_y, mid_y - (y + h))
            if excess > 2:
                add(
                    "overflow",
                    f"PDF word bounding box extends {excess:.1f} pt beyond the text frame.",
                    "Check surrounding content in the PNG and increase the text frame.",
                    "major",
                )
            run = shape.find(".//{*}rPr")
            color = run.find("{*}solidFill/{*}srgbClr") if run is not None else None
            background = next((c for b, c in reversed(layers) if contains(b, bounds, 0.05)), None)
            if color is not None and background:
                a, b = sorted((luminance(color.get("val")), luminance(background)))
                ratio = (b + 0.05) / (a + 0.05)
                size = int(run.get("sz", "0")) / 100
                bold = run.get("b") in ("1", "true")
                limit = 3 if size >= 18 or bold and size >= 14 else 4.5
                if ratio < limit:
                    add(
                        "low-contrast",
                        f"Foreground/background contrast {ratio:.2f}:1, minimum {limit}:1.",
                        "Choose a higher-contrast foreground or solid background.",
                    )
    return issues


def pdf_pages(pdf):
    # Poppler can emit invalid UTF-8 in XHTML metadata for supplementary characters.
    # The body is an independent XML document and contains all page/word geometry.
    xhtml = command("pdftotext", "-bbox", pdf, "-").stdout
    _, start, tail = xhtml.partition(b"<body>")
    body, end, _ = tail.rpartition(b"</body>")
    if not start or not end:
        raise ValueError("Missing PDF word geometry")
    return ET.fromstring(body).findall("{*}page")


def pdf_fonts(*args):
    return command("pdffonts", *args).stdout.decode(errors="replace").splitlines()[2:]


def placeholder_fonts(rows):
    names = [row.split()[0].rsplit("+", 1)[-1] for row in rows if row.strip()]
    return sorted({name for name in names if name.split("-")[0] in ("LastResort", "LastResortHE")})


def review_status(report):
    if any(i["severity"] == "blocker" and i["source"] == "deterministic" for i in report["issues"]):
        return "blocked"
    if report["issues"] or report.get("renderWarning") or report["critic"]["status"] == "unavailable":
        return "needs_review"
    return "checked"


def review(work, output):
    if any(output.iterdir()):
        raise ValueError("Review output must be an empty directory")
    start = time.monotonic()
    pptx = work / "deck.pptx"
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    slides = manifest["slides"]
    report = {
        "schemaVersion": 1,
        "deckId": manifest["deckId"],
        "pptxSha256": digest(pptx),
        "status": "preview_unavailable",
        "critic": {"status": "not_requested"},
        "pages": [],
        "issues": [],
    }
    try:
        if not 1 <= len(slides) <= 20:
            raise ValueError("Invalid source slide count")
        office = shutil.which("soffice") or "libreoffice"
        report["renderer"] = command(office, "--version").stdout.decode().strip()
        report["rasterizer"] = command("pdftoppm", "-v").stderr.decode().splitlines()[0]
        with tempfile.TemporaryDirectory() as profile:
            result = command(
                office,
                "-env:UserInstallation=" + Path(profile).as_uri(),
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                output,
                pptx,
            )
            if result.stderr.strip():
                report["renderWarning"] = result.stderr.decode(errors="replace")[:1000]
        pdf = output / "deck.pdf"
        if not pdf.is_file() or not pdf.stat().st_size:
            raise ValueError("LibreOffice did not produce a PDF")
        report["pdfSha256"] = digest(pdf)
        pages = pdf_pages(pdf)
        with zipfile.ZipFile(pptx) as archive:
            count = len(ET.fromstring(archive.read("ppt/presentation.xml")).findall(".//{*}sldId"))
            if len(pages) != len(slides) or count != len(pages):
                raise ValueError(f"Source/PPTX/PDF page counts: {len(slides)}/{count}/{len(pages)}")
            command("pdftoppm", "-png", "-scale-to", "1600", pdf, output / "slide")
            pngs = sorted(output.glob("slide-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
            if [int(p.stem.split("-")[-1]) for p in pngs] != list(range(1, count + 1)):
                raise ValueError("Incomplete or misnumbered PNG output")
            report["fonts"] = pdf_fonts(pdf)
            has_placeholders = bool(placeholder_fonts(report["fonts"]))
            sheet = Image.new("RGB", (320 * min(count, 3), 180 * ((count + 2) // 3)), "white")
            for i, (slide, page, png) in enumerate(zip(slides, pages, pngs)):
                words = [
                    (node.text or "", tuple(float(node.get(k)) for k in ("xMin", "yMin", "xMax", "yMax")))
                    for node in page.findall("{*}word")
                ]
                native = ET.fromstring(archive.read(f"ppt/slides/slide{i + 1}.xml"))
                rels = ET.fromstring(archive.read(f"ppt/slides/_rels/slide{i + 1}.xml.rels"))
                with Image.open(png) as image:
                    if image.size != (1600, 900):
                        raise ValueError("Unexpected page dimensions")
                    issues = inspect_page(
                        slide, words, native, archive, {r.get("Id"): r.get("Target") for r in rels}, image
                    )
                    if has_placeholders and not any(item["kind"] == "missing-glyph" for item in issues):
                        number = str(i + 1)
                        fonts = placeholder_fonts(pdf_fonts("-f", number, "-l", number, pdf))
                        if fonts:
                            issues.append(
                                issue(
                                    slide["slideId"],
                                    None,
                                    "missing-glyph",
                                    "PDF page uses a placeholder font: " + ", ".join(fonts) + ".",
                                    "Inspect the PNG and use a font that covers the original characters.",
                                )
                            )
                    sheet.paste(
                        image.resize((320, 180), getattr(Image, "Resampling", Image).LANCZOS),
                        (320 * (i % 3), 180 * (i // 3)),
                    )
                report["pages"].append({"slideId": slide["slideId"], "png": png.name, "sha256": digest(png)})
                report["issues"].extend(issues)
            sheet.save(output / "contact.png")
        report["contactSheet"] = "contact.png"
        alias = os.getenv("BISCUIT_PRESENTATION_CRITIC")
        if alias:
            # Preserve completed local results if a provider hangs and the worker is stopped.
            report["critic"] = {"status": "unavailable", "modelAlias": alias, "checkedSlides": []}
            report["status"] = review_status(report)
            save_report(output, report, start)
            from .presentation_critic import inspect_render

            inspect_render(report, manifest, output, alias)
        report["status"] = review_status(report)
    except (
        OSError,
        ValueError,
        KeyError,
        AttributeError,
        ET.ParseError,
        zipfile.BadZipFile,
        subprocess.SubprocessError,
    ) as exc:
        report["error"] = str(exc)[:400]
    save_report(output, report, start)
    return report


def save_report(output, report, start):
    report["durationMs"] = round((time.monotonic() - start) * 1000)
    pending = output / "report.tmp"
    pending.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(output / "report.json")
