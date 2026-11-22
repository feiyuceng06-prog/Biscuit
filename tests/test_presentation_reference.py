import tempfile
import unittest
import zipfile
from pathlib import Path

from feiyu.presentation_reference import inspect_reference


class ReferenceTests(unittest.TestCase):
    def test_library_sample_exposes_only_aggregate_visual_rules(self):
        sample = Path(__file__).resolve().parents[1] / "docs/presentation/evidence/before/monthly.pptx"
        result = inspect_reference(sample)
        self.assertEqual(result["slideCount"], 5)
        self.assertTrue(result["hasCharts"] and result["hasImages"])
        self.assertEqual(result["palette"], "light")
        self.assertEqual(result["titleAlignment"], "left")
        self.assertRegex(result["id"], "^pptx-[0-9a-f]{64}$")
        self.assertNotIn("闭馆", str(result))

    def test_empty_or_oversized_slide_collection_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reference.pptx"
            for count in (0, 101):
                with zipfile.ZipFile(path, "w") as archive:
                    for i in range(count):
                        archive.writestr(f"ppt/slides/slide{i + 1}.xml", "<sld/>")
                with self.assertRaises(ValueError):
                    inspect_reference(path)
