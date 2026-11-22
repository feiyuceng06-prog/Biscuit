import json
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from feiyu import presentation_review
from feiyu.presentation_critic import inspect_render, validate
from feiyu.presentation_review import review

SAMPLE = Path(__file__).resolve().parents[1] / "docs/presentation/evidence/before"
requires_renderer = unittest.skipUnless(
    (shutil.which("soffice") or shutil.which("libreoffice"))
    and all(shutil.which(x) for x in ("pdftoppm", "pdftotext", "pdffonts")),
    "requires Impress and Poppler",
)


def rewrite_export(destination, edit, *, title=None):
    with zipfile.ZipFile(SAMPLE / "monthly.pptx") as src, zipfile.ZipFile(destination, "w") as dst:
        for entry in src.infolist():
            data = src.read(entry)
            if entry.filename == "ppt/slides/slide1.xml":
                page = ET.fromstring(data)
                edit(*(s for s in page.findall(".//{*}sp") if s.find("{*}txBody") is not None))
                data = ET.tostring(page, encoding="utf-8")
            if entry.filename == "docProps/core.xml" and title:
                metadata = ET.fromstring(data)
                metadata.find("{*}title").text = title
                data = ET.tostring(metadata, encoding="utf-8")
            dst.writestr(entry, data)


def narrow_frame(body, width):
    body.find(".//{*}xfrm/{*}ext").set("cx", str(width * 12700))
    frame = body.find(".//{*}bodyPr")
    frame.set("wrap", "none")
    frame.remove(frame.find("{*}normAutofit"))


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

    def test_successful_conversion_command_without_pdf_is_unavailable(self):
        shutil.copyfile(SAMPLE / "monthly.pptx", self.deck)
        result = SimpleNamespace(stdout=b"LibreOffice", stderr=b"renderer diagnostic")
        with patch("feiyu.presentation_review.command", return_value=result):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "preview_unavailable")
        self.assertEqual(report["error"], "LibreOffice did not produce a PDF")
        self.assertEqual(report["renderWarning"], "renderer diagnostic")

    @requires_renderer
    def test_exported_photo_crop_and_position_are_checked_against_the_plan(self):
        sample = SAMPLE.parents[1] / "phase-3/acceptance/portrait"
        shutil.copyfile(sample / "manifest.json", self.work / "manifest.json")
        with zipfile.ZipFile(sample / "deck.pptx") as source, zipfile.ZipFile(self.deck, "w") as output:
            for entry in source.infolist():
                data = source.read(entry)
                if entry.filename == "ppt/slides/slide1.xml":
                    page = ET.fromstring(data)
                    pictures = page.findall(".//{*}pic")
                    pictures[0].find(".//{*}srcRect").set("l", "0")
                    pictures[1].find(".//{*}xfrm/{*}off").set("x", str(200 * 12700))
                    data = ET.tostring(page, encoding="utf-8")
                output.writestr(entry, data)
        with patch.dict(os.environ, BISCUIT_PRESENTATION_CRITIC=""):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual({issue["kind"] for issue in report["issues"]}, {"image-crop", "image-position"})

    @requires_renderer
    def test_actual_export_corruption(self):
        def damage(label, title, body, folio):
            label.find(".//{*}rPr/{*}solidFill/{*}srgbClr").set("val", "FBF6EB")
            title.find(".//{*}t").text = "闭馆"
            narrow_frame(body, 160)
            folio.find(".//{*}xfrm/{*}off").set("x", str(950 * 12700))

        rewrite_export(self.deck, damage)
        with patch.dict(os.environ, BISCUIT_PRESENTATION_CRITIC=""):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "blocked", report)
        self.assertEqual(len(report["pages"]), 5)
        defects = {i["kind"] for i in report["issues"] if i["slideId"] == "monthly-1"}
        self.assertTrue(
            {"low-contrast", "missing-text", "out-of-bounds", "clipping", "overflow"} <= defects, defects
        )
        self.assertTrue((self.output / report["contactSheet"]).is_file())

    @requires_renderer
    def test_supplementary_metadata_does_not_hide_overflow_and_small_text_contrast(self):
        def damage(label, title, body, folio):
            narrow_frame(body, 80)
            style = label.find(".//{*}rPr")
            style.set("sz", "800")
            style.find("{*}solidFill/{*}srgbClr").set("val", "8E8576")

        rewrite_export(self.deck, damage, title="案例 𠮷 😀")
        with patch.dict(os.environ, BISCUIT_PRESENTATION_CRITIC=""):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "blocked", report)
        self.assertEqual(len(report["pages"]), 5)
        issues = {
            (tuple(i["elementIds"]), i["kind"]) for i in report["issues"] if i["slideId"] == "monthly-1"
        }
        self.assertIn((("text-0",), "overflow"), issues)
        self.assertNotIn((("text-0",), "clipping"), issues)
        self.assertIn((("label-0",), "low-contrast"), issues)

    @requires_renderer
    def test_placeholder_font_is_reported_on_the_affected_page(self):
        shutil.copyfile(SAMPLE / "monthly.pptx", self.deck)
        pdf_fonts = presentation_review.pdf_fonts

        def fonts(*args):
            if len(args) == 1 or args[1] == "2":
                return pdf_fonts(*args) + ["AAAAAA+LastResortHE-Regular TrueType WinAnsi yes yes yes 1 0"]
            return pdf_fonts(*args)

        with (
            patch("feiyu.presentation_review.pdf_fonts", side_effect=fonts),
            patch.dict(os.environ, BISCUIT_PRESENTATION_CRITIC=""),
        ):
            report = review(self.work, self.output)
        findings = [i for i in report["issues"] if i["kind"] == "missing-glyph"]
        self.assertEqual([(i["slideId"], i["elementIds"]) for i in findings], [("monthly-2", [])])
        self.assertIn("LastResortHE-Regular", findings[0]["evidence"])
        self.assertEqual(report["status"], "blocked")

    @requires_renderer
    def test_misnumbered_pngs_never_bind_to_slide_ids(self):
        shutil.copyfile(SAMPLE / "monthly.pptx", self.deck)
        command = presentation_review.command

        def misnumber(*args):
            result = command(*args)
            if args[:2] == ("pdftoppm", "-png"):
                (self.output / "slide-2.png").rename(self.output / "slide-6.png")
            return result

        with patch("feiyu.presentation_review.command", side_effect=misnumber):
            report = review(self.work, self.output)
        self.assertEqual(report["status"], "preview_unavailable")
        self.assertIn("misnumbered PNG", report["error"])
        self.assertEqual(report["pages"], [])

    @requires_renderer
    def test_interrupted_critic_leaves_preflight_marked_for_review(self):
        shutil.copyfile(SAMPLE / "monthly.pptx", self.deck)
        with (
            patch.dict(os.environ, BISCUIT_PRESENTATION_CRITIC="offline"),
            patch("feiyu.presentation_review.inspect_page", return_value=[]),
            patch("feiyu.presentation_critic.inspect_render", side_effect=SystemExit(124)),
            self.assertRaises(SystemExit),
        ):
            review(self.work, self.output)
        report = json.loads((self.output / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["critic"]["status"], "unavailable")
        self.assertEqual(len(report["pages"]), 5)

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

    def test_short_json_reply_is_scoped_to_official_deepseek_flash(self):
        from feiyu.providers import OpenAICompatBackend

        reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"issues":[]}'))])
        for model, host, requested, expected in [
            ("deepseek-flash", "api.deepseek.com", True, True),
            ("deepseek-flash", "api.deepseek.com", False, False),
            ("deepseek-flash", "other.example", True, False),
            ("another-model", "api.deepseek.com", True, False),
        ]:
            with self.subTest(model=model, host=host, requested=requested):
                backend = OpenAICompatBackend(model=model, base_url="https://" + host, api_key="fixture",
                                              system="", tools=[])
                with backend.client, patch.object(backend, "_sdk_call", return_value=reply) as call:
                    self.assertEqual(backend.ask("JSON", json_reply=requested), '{"issues":[]}')
                    self.assertEqual(call.call_args.kwargs.get("response_format"),
                                     {"type": "json_object"} if expected else None)
                    self.assertEqual(call.call_args.kwargs.get("extra_body"),
                                     {"thinking": {"type": "disabled"}} if expected else None)

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
