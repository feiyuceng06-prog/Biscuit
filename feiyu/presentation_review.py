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
        "issueId": f"{page}:{element}:{kind}",
        "slideId": page,
        "elementIds": [element],
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


def inspect_page(slide, words, native, archive, relationships, image):
    page = slide["slideId"]
    issues, layers, text_frames = [], [], []
    shapes = [s for s in native.find(".//{*}spTree") if s.tag.split("}")[-1] in ("sp", "pic", "graphicFrame")]
    if len(shapes) != len(slide["objects"]):
        issues.append(
            issue(
                page,
                "page",
                "object-count",
                f"{len(shapes)} PPTX objects, expected {len(slide['objects'])}",
                "Re-export the complete page.",
            )
        )
    if image.convert("RGB").getcolors(1) is not None:
        issues.append(
            issue(page, "page", "blank", "The raster has one unique colour.", "Inspect slide visibility.")
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
                    if asset.width < w / 2 or asset.height < h / 2:
                        add(
                            "low-resolution",
                            f"{asset.width} × {asset.height} px in {w:g} × {h:g} pt.",
                            "Supply a larger source image.",
                            "major",
                        )
            except (KeyError, ValueError, OSError, SyntaxError):
                add("missing-image", "Embedded image cannot be decoded.", "Reattach the original image.")
        elif kind in ("text", "chart"):
            # Match word centres, since Poppler ascent/descent includes space outside the ink.
            local = [(v, b) for v, b in words if contains(bounds, word_center(b), 2)]
            content = normalized("".join(v for v, _ in local))
            if kind == "chart":
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
            if text and text not in content:
                add(
                    "clipping",
                    "Expected text is incomplete in PDF words inside the PPTX text box.",
                    "Inspect the PNG and enlarge or reposition the text box.",
                    "major",
                )
            if "\ufffd" in content or any(ord(c) < 32 for c in content):
                add(
                    "missing-glyph",
                    "Rendered text contains a replacement or control character.",
                    "Check the original character and font coverage.",
                )
            excess = max(
                (max(x - b[0], b[2] - x - w, (b[1] + b[3]) / 2 - y - h) for _, b in local), default=0
            )
            if excess > 2:
                add(
                    "overflow",
                    f"PDF word bounding box extends {excess:.1f} pt beyond the text frame.",
                    "Check surrounding content in the PNG and increase the text frame.",
                    "major",
                )
            color = shape.find(".//{*}rPr/{*}solidFill/{*}srgbClr")
            background = next((c for b, c in reversed(layers) if contains(b, bounds, 0.05)), None)
            if color is not None and background:
                a, b = sorted((luminance(color.get("val")), luminance(background)))
                ratio = (b + 0.05) / (a + 0.05)
                limit = 3 if expected["size"] >= 18 or expected["bold"] and expected["size"] >= 14 else 4.5
                if ratio < limit:
                    add(
                        "low-contrast",
                        f"Foreground/background contrast {ratio:.2f}:1, minimum {limit}:1.",
                        "Choose a higher-contrast foreground or solid background.",
                    )
    return issues


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
        report["pdfSha256"] = digest(pdf)
        pages = ET.fromstring(command("pdftotext", "-bbox", pdf, "-").stdout).findall(".//{*}page")
        with zipfile.ZipFile(pptx) as archive:
            count = len(ET.fromstring(archive.read("ppt/presentation.xml")).findall(".//{*}sldId"))
            if len(pages) != len(slides) or count != len(pages):
                raise ValueError(f"Source/PPTX/PDF page counts: {len(slides)}/{count}/{len(pages)}")
            command("pdftoppm", "-png", "-scale-to", "1600", pdf, output / "slide")
            pngs = sorted(output.glob("slide-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
            if len(pngs) != count:
                raise ValueError("Incomplete PNG output")
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
                    sheet.paste(
                        image.resize((320, 180), getattr(Image, "Resampling", Image).LANCZOS),
                        (320 * (i % 3), 180 * (i // 3)),
                    )
                report["pages"].append({"slideId": slide["slideId"], "png": png.name, "sha256": digest(png)})
                report["issues"].extend(issues)
            sheet.save(output / "contact.png")
        report["contactSheet"] = "contact.png"
        report["fonts"] = command("pdffonts", pdf).stdout.decode(errors="replace").splitlines()[2:]
        if any(i["severity"] == "blocker" for i in report["issues"]):
            report["status"] = "blocked"
        elif report["issues"] or report.get("renderWarning"):
            report["status"] = "needs_review"
        else:
            report["status"] = "checked"
        alias = os.getenv("BISCUIT_PRESENTATION_CRITIC")
        if alias:
            from .presentation_critic import inspect_render

            # Preserve completed local results if a provider hangs and the worker is stopped.
            report["critic"] = {"status": "unavailable", "modelAlias": alias}
            save_report(output, report, start)
            inspect_render(report, manifest, output, alias)
            if report["status"] == "checked" and (
                report["issues"] or report["critic"]["status"] != "checked"
            ):
                report["status"] = "needs_review"
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
