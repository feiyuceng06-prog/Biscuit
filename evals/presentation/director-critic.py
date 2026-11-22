"""Run Biscuit's configured Visual Critic on each rendered page of a frozen A/B set.

Run with python -m evals.presentation.director-critic EVIDENCE MODEL_ALIAS.
Per-page reports keep a provider failure on one slide from masking the remaining pages.
"""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from feiyu.presentation_critic import inspect_render


def inspect_one(job):
    folder, report, manifest, page, slide, alias = job
    assert hashlib.sha256((folder / page["png"]).read_bytes()).hexdigest() == page["sha256"]
    local = {
        **report,
        "pages": [page],
        "issues": [i for i in report["issues"] if i["source"] == "deterministic"],
    }
    inspect_render(local, {**manifest, "slides": [slide]}, folder, alias)
    return {
        "slideId": slide["slideId"],
        "sha256": page["sha256"],
        **local["critic"],
        "issues": [i for i in local["issues"] if i["source"] == "vision-model"],
    }


def run(root, alias):
    with ThreadPoolExecutor(max_workers=3) as pool:
        batches = []
        for path in sorted(root.glob("*/*/review/report.json")):
            report = json.loads(path.read_text())
            manifest = json.loads((path.parents[1] / "manifest.json").read_text())
            assert len(report["pages"]) == len(manifest["slides"])
            calls = [
                pool.submit(inspect_one, (path.parent, report, manifest, page, slide, alias))
                for page, slide in zip(report["pages"], manifest["slides"])
            ]
            batches.append((path, calls))
        for path, calls in batches:
            pages = [future.result() for future in calls]
            (path.parent / "critic-pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n")
            print(path.parent, [page["status"] for page in pages], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("alias")
    args = parser.parse_args()
    run(args.root, args.alias)
