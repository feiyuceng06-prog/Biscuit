# Biscuit display-name compatibility (0.87.1)

Biscuit is the new product display name. Author Feiyu, repository URLs, Python/CLI
names, environment/IPC/storage keys, npm/deb package identity, executable name
`feiyu-desktop`, and appId `com.feiyuz.feiyu` are retained. The logo is unchanged.

Before changing display names, actual source and old-name Linux packaged Electron
were measured with synthetic HOME/XDG directories: app name `feiyu-desktop`,
userData `<appData>/feiyu-desktop` in both cases. The main process now pins that
userData directory before setting its display name to Biscuit. No real user data
is moved or rewritten. A synthetic old-name packaged application creates workspace,
theme and Chinese conversation data; after replacing only the application payload
at the same path, Biscuit must find the same userData, remember the workspace,
restore the theme/history and send with retained conversation context.

NSIS uses unchanged appId-derived GUID, unchanged internal package/executable name
and installation directory identity. Display/shortcut names become Biscuit. Native
CI builds an old-name installer fixture from exact UI commit0105edef8361908284707c47c390b7918864a813;
its 59 backend source files must equal review baseline6a1b775. It embeds the current
frozen backend from the current release commit. Since the e1da222 ACL fix, that
backend differs from the 59-file historical baseline. This tests old UI/install
identity with the current backend, not a historical backend or published Windows release. That fixture
installs only to runner scratch. Biscuit is then installed without `/D`, requiring
NSIS to discover the same existing installation. CI checks registry identity,
display name, installation location, shortcut target/name and retained synthetic data.
Full installed GUI and bundled shell tests still run afterwards.

`get.sh` accepts old Feiyu and new Biscuit AppImages. API asset discovery is name
agnostic; the rate-limit fallback probes Biscuit then Feiyu for the actual release
tag. The 0.87.1 README describes the release being prepared; published 0.87.0
asset names remain unchanged in that historical release. No historical release is edited.

Brand compatibility does not resolve the separate existing snapshot explicit-ACL
privacy boundary observed by the independent Windows probe (exit20). No reviewed
storage implementation changes are part of this rename.
