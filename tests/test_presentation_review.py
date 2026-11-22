import json
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

from feiyu.presentation_critic import inspect_render, validate
from feiyu.presentation_review import review

SAMPLE = Path(__file__).resolve().parents[1] / "docs/presentation/evidence/before"


def damage_export(destination):
    """Mutate native objects so the real renderer sees defects absent in the manifest."""
    with zipfile.ZipFile(SAMPLE / "monthly.pptx") as src, zipfile.ZipFile(destination, "w") as dst:
        for entry in src.infolist():
            data = src.read(entry)
            if entry.filename == "ppt/slides/slide1.xml":
                page = ET.fromstring(data)
                label, title, body, folio = [
                    s for s in page.findall(".//{*}sp") if s.find("{*}txBody") is not None
                ]
                # The label becomes nearly indistinguishable from the sand canvas.
                label.find(".//{*}rPr/{*}solidFill/{*}srgbClr").set("val", "FBF6EB")
                title.find(".//{*}t").text = "闭馆"  # two characters removed in the actual file
                body.find(".//{*}xfrm/{*}ext").set("cx", str(160 * 12700))
                frame = body.find(".//{*}bodyPr")
                frame.set("wrap", "none")
                frame.remove(frame.find("{*}normAutofit"))
                folio.find(".//{*}xfrm/{*}off").set("x", str(950 * 12700))
                data = ET.tostring(page, encoding="utf-8")
            dst.writestr(entry, data)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.output = self.work / "output"
        self.output.mkdir()
        shutil.copyfile(SAMPLE / "monthly.manifest.json", self.work / "manifest.json")
        self.deck = self.work / "deck.pptx"

    def test_render_failure_never_passes_or_destroys_export(self):
        shutil.copyfile(SAMPLE / "monthly.pptx", self.deck)
        with patch("feiyu.presentation_review.command", side_effect=FileNotFoundError("soffice")):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "preview_unavailable")
        self.assertEqual(self.deck.read_bytes(), (SAMPLE / "monthly.pptx").read_bytes())
        self.assertFalse(report["pages"])
        self.assertTrue((self.output / "report.json").is_file())
        with self.assertRaises(ValueError):
            review(self.work, self.output)

    @unittest.skipUnless(
        all(shutil.which(x) for x in ("soffice", "pdftoppm", "pdftotext", "pdffonts")),
        "requires Impress and Poppler",
    )
    def test_actual_export_corruption(self):
        damage_export(self.deck)
        with patch.dict(os.environ, BISCUIT_PRESENTATION_CRITIC=""):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "blocked", report)
        self.assertEqual(len(report["pages"]), 5)
        defects = {i["kind"] for i in report["issues"] if i["slideId"] == "monthly-1"}
        self.assertTrue(
            {"low-contrast", "missing-text", "out-of-bounds", "clipping", "overflow"} <= defects, defects
        )
        self.assertTrue((self.output / report["contactSheet"]).is_file())

    def test_critic_sends_page_and_sheet_through_configured_sdks(self):
        from tests.test_sdk_worker import SDKWorkerTests

        source = SAMPLE / "monthly-2.png"
        # Different bytes distinguish the actual page from the deck overview.
        from PIL import Image

        with Image.open(source) as im:
            im.thumbnail((320, 180))
            im.save(self.output / "contact.png")
        shutil.copyfile(source, self.output / "page.png")
        slide = {"slideId": "s", "objects": [{"id": "title"}]}
        issue = {
            "slideId": "s",
            "elementIds": ["title"],
            "kind": "poor-alignment",
            "severity": "minor",
            "confidence": 0.7,
            "evidence": "Top right title frame.",
            "suggestedChange": "Align to the text column.",
        }
        for anthropic in (False, True):
            with SDKWorkerTests().server("complete", anthropic, ask_text=json.dumps({"issues": [issue]})) as (
                url,
                _,
                requests,
            ):
                entry = {
                    "kind": "anthropic" if anthropic else "openai",
                    "key": "offline",
                    "model": "fixture",
                    "base_url": url,
                    "vision": True,
                }
                report = {
                    "contactSheet": "contact.png",
                    "renderer": "Impress",
                    "fonts": [],
                    "issues": [],
                    "pages": [{"slideId": "s", "png": "page.png"}],
                }
                with patch("feiyu.presentation_critic.keys.load", return_value={"fixture": entry}):
                    inspect_render(report, {"brief": "Synthetic", "slides": [slide]}, self.output, "fixture")
                self.assertEqual(report["critic"]["status"], "checked", report)
                self.assertEqual(report["issues"][0]["source"], "vision-model")
                parts = requests[0]["messages"][0]["content"]
                image_type = "image" if anthropic else "image_url"
                self.assertEqual([p["type"] for p in parts], ["text", image_type, image_type])
                self.assertNotEqual(parts[1], parts[2])
                self.assertNotIn("tools", requests[0])

    def test_critic_requires_valid_evidence_and_ids(self):
        slide = {"slideId": "s", "objects": [{"id": "title"}]}
        finding = {
            "slideId": "s",
            "elementIds": ["title"],
            "severity": "minor",
            "kind": "crowded",
            "confidence": 0.8,
            "evidence": "Title touches the top edge.",
            "suggestedChange": "Add space above it.",
        }
        self.assertEqual(validate(json.dumps({"issues": [finding]}), slide)[0]["source"], "vision-model")
        for change in (
            {"elementIds": ["unknown"]},
            {"confidence": True},
            {"evidence": ""},
            {"slideId": "unknown"},
        ):
            with self.assertRaises(ValueError):
                validate(json.dumps({"issues": [finding | change]}), slide)
        report = {}
        with patch("feiyu.presentation_critic.keys.load", return_value={}):
            inspect_render(report, {}, self.output, "missing")
        self.assertEqual(report["critic"]["status"], "unavailable")
