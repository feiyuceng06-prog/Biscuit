"""Verify the archived Studio runs against input files and package relationships (run at repo root)."""
import base64
import hashlib
import json
import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SUITE = Path(__file__).resolve().parent
EVIDENCE = Path("docs/presentation/photography-pilot")
cases = {case["id"]: case for case in json.loads((SUITE / "cases.json").read_text())["cases"]}
sources = {s["objectID"]: s for s in json.loads((SUITE / "sources.json").read_text())}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(run):
    log = json.loads((run / "run.json").read_text())
    result = dict(seconds=log["totalMs"] / 1000, manualPageEdits=log["manualPageEdits"],
                  generationRetries=sum(e.get("attempt", 0) > 1 for e in log["events"]))
    if "failure" in log:
        return dict(result, failure=log["failure"].splitlines()[0])
    case = cases[log["name"]]
    deck = json.loads((run / "source.deck.json").read_text())
    report_path, = run.glob("*.review-*/report.json")
    report = json.loads(report_path.read_text())
    pptx = run / "deck.pptx"
    assert report["deckId"] == deck["id"] and sha(pptx.read_bytes()) == report["pptxSha256"]
    assert len(deck["slides"]) == len(report["pages"]) == case["pages"]
    assert deck["slides"][0]["title"] == case["title"]
    if "copy" in case:
        assert case["copy"] in [i["text"] for i in deck["slides"][-1]["items"]]
    final_editions = {"river-3", "pair-3", "reading-7", "reading-8"}
    ids = []
    pages = []
    with zipfile.ZipFile(pptx) as pkg:
        for n, (slide, page) in enumerate(zip(deck["slides"], report["pages"]), 1):
            png = report_path.parent / page["png"]
            assert page["slideId"] == slide["id"] and sha(png.read_bytes()) == page["sha256"]
            root = ET.fromstring(pkg.read(f"ppt/slides/slide{n}.xml"))
            rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(pkg.read(f"ppt/slides/_rels/slide{n}.xml.rels"))}
            original = slide.get("photos", [])
            pics = root.findall(".//{*}pic")
            assert len(original) == len(pics)
            texts = ["".join(node.itertext()) for node in root.findall(".//{*}t")]
            for field in [slide["title"], *(i[k] for i in slide["items"] for k in ("label", "text") if i[k])]:
                assert field in texts
            notes = "".join(ET.fromstring(pkg.read(f"ppt/notesSlides/notesSlide{n}.xml")).itertext())
            missing = []
            for photo, pic in zip(original, pics):
                ident = int(Path(photo["name"]).stem)
                ids.append(ident)
                blip = pic.find(".//{*}blip")
                rid = next(v for k, v in blip.attrib.items() if k.endswith("}embed"))
                embedded = pkg.read(posixpath.normpath(posixpath.join("ppt/slides", rels[rid])))
                assert embedded == base64.b64decode(photo["data"].split(",")[1])
                if sources[ident]["objectURL"] not in notes:
                    missing.append(ident)
            if run.name in final_editions:
                assert not missing, f"Missing original references on page {n}"
            if run.name in {"reading-7", "reading-8"} and n == 2:
                assert slide["layout"] == "comparison" and len(original) == len(slide["items"]) == 2
                for photo, item in zip(original, slide["items"]):
                    record = sources[int(Path(photo["name"]).stem)]
                    width, height = record["dimensions"]
                    assert item["label"] == ("竖幅" if height > width else "横幅")
                    assert item["text"] == record["title"]
            pages.append(dict(png=str(png.relative_to(EVIDENCE)), sha256=page["sha256"],
                              photoIDs=[p["name"] for p in original], missingURLs=missing))
    assert ids == case["photos"]
    for record in sources.values():
        assert record["jpegSha256"] == sha((SUITE / "media" / f"{record['objectID']}.jpg").read_bytes())
    return dict(result, status=report["status"], issues=[i["kind"] for i in report["issues"]],
                repairAttempts=report.get("repairAttempts", 0), pptxSHA=report["pptxSha256"], pages=pages)


if __name__ == "__main__":
    print(json.dumps({r.name: verify(r) for r in sorted((EVIDENCE / "runs").iterdir())}, ensure_ascii=False, indent=2))
