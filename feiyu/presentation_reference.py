"""Extract aggregate visual cues from a user-selected PPTX, without importing its content."""

import hashlib
import io
import re
import statistics
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def inspect_reference(path: Path):
    with path.open("rb") as stream:
        data = stream.read(16 * 1024**2 + 1)
    if len(data) > 16 * 1024**2:
        raise ValueError("参考 PPTX 最大为 16 MB")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        slides = [
            entry
            for entry in archive.infolist()
            if re.fullmatch(r"ppt/slides/slide[1-9]\d*\.xml", entry.filename)
        ]
        if not 1 <= len(slides) <= 100 or sum(entry.file_size for entry in slides) > 12 * 1024**2:
            raise ValueError("参考文稿应为 1–100 页，页面 XML 总量不超过 12 MB")

        def xml(entry):
            with archive.open(entry) as stream:
                raw = stream.read(2 * 1024**2 + 1)
            declarations = raw.replace(b"\x00", b"").upper()
            if len(raw) > 2 * 1024**2 or b"<!DOCTYPE" in declarations or b"<!ENTITY" in declarations:
                raise ValueError("参考文稿 XML 不支持或过大")
            return ET.fromstring(raw)

        size = xml("ppt/presentation.xml").find("{*}sldSz")
        if size is None:
            raise ValueError("参考文稿缺少页面尺寸")
        width, height = int(size.attrib["cx"]), int(size.attrib["cy"])
        counts, alignments, backgrounds = [], [], []
        charts = images = False
        for entry in slides:
            slide = xml(entry)
            charts |= slide.find(".//{*}chart") is not None
            images |= slide.find(".//{*}pic") is not None
            counts.append(sum(len(t.text or "") for t in slide.findall(".//{*}txBody//{*}t")))
            candidates = []
            background = slide.find(".//{*}bgPr/{*}solidFill/{*}srgbClr")
            for shape in slide.findall(".//{*}sp"):
                extent = shape.find("./{*}spPr/{*}xfrm/{*}ext")
                if extent is not None and width > 0 and height > 0:
                    if (
                        int(extent.get("cx", "0")) >= width * 0.98
                        and int(extent.get("cy", "0")) >= height * 0.98
                    ):
                        fill = shape.find("./{*}spPr/{*}solidFill/{*}srgbClr")
                        if fill is not None:
                            background = fill
                body = shape.find("{*}txBody")
                if body is None or body.find(".//{*}t") is None:
                    continue
                placeholder = shape.find(".//{*}ph")
                title = placeholder is not None and placeholder.get("type") in ("title", "ctrTitle")
                max_size = max((int(r.get("sz", "0")) for r in body.findall(".//{*}rPr")), default=0)
                para = body.find(".//{*}pPr")
                align = para.get("algn", "l") if para is not None else "l"
                candidates.append((title, max_size, align))
            if candidates:
                alignments.append(max(candidates, key=lambda candidate: candidate[:2])[2])
            rgb = background.get("val", "") if background is not None else ""
            if re.fullmatch("[0-9A-Fa-f]{6}", rgb):
                brightness = sum(
                    int(rgb[i : i + 2], 16) * k for i, k in ((0, 0.2126), (2, 0.7152), (4, 0.0722))
                )
                backgrounds.append("light" if brightness >= 140 else "dark")

    density = statistics.median(counts)

    def dominant(values):
        if values and values.count(values[0]) == len(values):
            return values[0]
        return "mixed"

    return {
        "id": "pptx-" + hashlib.sha256(data).hexdigest(),
        "name": path.stem[:80],
        "slideCount": len(slides),
        "textDensity": "sparse" if density < 65 else "dense" if density > 180 else "balanced",
        "hasCharts": charts,
        "hasImages": images,
        "titleAlignment": {"l": "left", "ctr": "center"}.get(dominant(alignments), "mixed"),
        "palette": dominant(backgrounds) if len(backgrounds) == len(slides) else "mixed",
    }
