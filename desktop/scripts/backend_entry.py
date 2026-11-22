"""Frozen desktop backend. Uses the same CLI/stdio entry point as feiyu."""
from feiyu.runtime import configure_frozen_environment

configure_frozen_environment()

import sys

if sys.platform == 'linux' and len(sys.argv) == 4 and sys.argv[1] == '--_job-supervisor':
    from feiyu.jobrunner import main as supervise_job
    raise SystemExit(supervise_job(sys.argv[2], sys.argv[3]))

if sys.platform == 'linux' and len(sys.argv) == 6 and sys.argv[1] == '--_sdk-supervisor':
    from feiyu.sdk_lifecycle import supervise
    raise SystemExit(supervise(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])))

if sys.argv[1:] == ['--_sdk-worker']:
    from feiyu.sdk_worker import worker_main
    raise SystemExit(worker_main())

if sys.argv[1:] == ['--_mcp-http-worker']:
    from feiyu.mcp import http_worker_main
    raise SystemExit(http_worker_main())

if len(sys.argv) == 5 and sys.argv[1] == '--_presentation-content-worker':
    from feiyu.presentation_content import worker_main
    raise SystemExit(worker_main(sys.argv[2:]))

from feiyu.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
