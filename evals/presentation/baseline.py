"""Measure the unmodified exporter and save reference pixels for later comparisons."""

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    exports = subprocess.check_output(["node", Path(__file__).with_name("export.mjs"), output], text=True)
    records = []
    with tempfile.TemporaryDirectory() as profile:
        for line in exports.splitlines():
            name, count, ms = line.split()
            start = time.monotonic()
            subprocess.run(
                [
                    "soffice",
                    "-env:UserInstallation=" + Path(profile).as_uri(),
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    output,
                    output / (name + ".pptx"),
                ],
                check=True,
                timeout=90,
            )
            subprocess.run(
                ["pdftoppm", "-png", "-scale-to", "1600", output / (name + ".pdf"), output / name],
                check=True,
                timeout=90,
            )
            pages = sorted(output.glob(name + "-*.png"))
            assert len(pages) == int(count)
            hashes = []
            for page in pages:
                with Image.open(page) as image:
                    assert image.size == (1600, 900) and image.convert("L").getextrema()[0] < 220
                hashes.append(hashlib.sha256(page.read_bytes()).hexdigest())
            records.append(
                {
                    "deck": name,
                    "pages": int(count),
                    "exportMs": int(ms),
                    "renderMs": round(1000 * (time.monotonic() - start)),
                    "pngSha256": hashes,
                }
            )
    (output / "baseline.json").write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
