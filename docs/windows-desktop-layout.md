# Windows desktop layout acceptance (0.87.1)

The preview defaults to open. Previously, at a content width of 1100 CSS pixels
or less it became a fixed overlay over the chat composer. On the Windows runner
this intercepted an ordinary Send click before the first conversation.

The preview now stays in its own grid column. At that breakpoint the session
sidebar is temporarily hidden while preview is open, leaving space for chat;
closing preview restores the sidebar. File preview and its controls remain usable.
No pointer events are disabled and Send still uses the normal click handler.

`tests/layout.mjs` checks input focus, normal Send click actionability, hit testing,
viewport containment and panel/composer separation at 800×560, 1024×768,
1100×768, 1101×768 and 1440×920 content sizes, with preview open and closed,
both empty and showing a file. Each case retains a screenshot and rectangle/hit
metadata. Windows source GUI repeats at Chromium native device scale factors
1, 1.25, 1.5 and 2; these are automated device-scale tests, not physical monitor or
Windows display-settings changes. Actual dimensions and devicePixelRatio are
recorded, and an unachievable requested size fails the test.

The normal GUI smoke sends synthetic Chinese/emoji streaming requests to loopback,
closes the application, restarts with `--resume`, verifies saved content and sends
a second turn with retained context and the same durable journal. Windows CI runs
this against source Electron, unpacked Electron and a temporary NSIS installation.
The installer never targets an existing user installation. Diagnostic artifacts
include a tracked-file SHA256 manifest bound to the commit and CI run.

Python matrix timeout is 30 minutes: the previous 15-minute limit cancelled
3.10/3.12, including a 3.10 run that printed OK but never recorded successful
process exit. No failures are allowed or suppressed.

SDK direct ask/stream and parent success are separate from cancellation. The
current POSIX silent-parent signal fixture does not establish Windows SDK parent
cancellation/reaping. Its output explicitly retains that gap. Required native
Windows persistence gates and frozen MCP cancellation remain separate checks.
