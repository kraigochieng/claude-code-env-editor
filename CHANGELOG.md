# CHANGELOG


## v0.6.0 (2026-10-10)

### Bug Fixes

- **envvars**: Let settings.json win over the shell environment
  ([`6048dde`](https://github.com/kraigochieng/claude-code-env-editor/commit/6048dde95641dbd3652df7330ad71670c7209f87))

I tested Claude Code with a fake local server: a model in the env block overrides ANTHROPIC_MODEL
  exported in the shell. The table, show, and verify now follow that. A different shell value shows
  as a note. The README and the help screen state the right order.

Refs #46

- **tui**: Show one question mark for help in the footer
  ([`acd714b`](https://github.com/kraigochieng/claude-code-env-editor/commit/acd714b776cbab64056a2276bdf1c46a03d6c397))

The key and the label both started with a question mark.

Refs #46

### Documentation

- Refresh the screenshots after the palette and paste hint changes
  ([`6017059`](https://github.com/kraigochieng/claude-code-env-editor/commit/60170591d8284f1381a0fdae357568231eabff2f))

Closes #44

- Say what claude code does and what this tool adds
  ([`fd1b9d3`](https://github.com/kraigochieng/claude-code-env-editor/commit/fd1b9d3175a8b43241a5fe4c70d04de4110de8e3))

Add the sections on built-in features, the added value, and the settings levels the tool cannot see.
  Refresh the screenshots.

Closes #46

### Features

- **tui**: Ask for confirmation before removing a variable
  ([`60d52e7`](https://github.com/kraigochieng/claude-code-env-editor/commit/60d52e7caed2b2d9da350b9ef348a8ebdfaccb70))

x opens a yes or no dialog. A value that only the shell holds is not removed, and the tool says so.

Refs #46

### Refactoring

- **envvars**: Remove the CLAUDE_CONFIG_DIR row
  ([`ceaaf6f`](https://github.com/kraigochieng/claude-code-env-editor/commit/ceaaf6f3b23092df9d65c4699584f9872da34d81))

The banner shows the config directory and d switches it. The row could not be edited. set now
  refuses that name with a hint.

Refs #46


## v0.5.1 (2026-10-10)

### Bug Fixes

- **tui**: Do not crash when the verify dialog closes before the checks end
  ([`742aaa5`](https://github.com/kraigochieng/claude-code-env-editor/commit/742aaa517751258e1b98a2ce77584fe90e7c593c))

The worker thread called update_body on a screen that was gone, and Textual raised NoMatches.
  update_body now does nothing on a closed dialog, and the worker ignores a closed app.

Closes #38

### Documentation

- Tell users to paste with ctrl+shift+v
  ([`1a0b6c9`](https://github.com/kraigochieng/claude-code-env-editor/commit/1a0b6c92f72040ba92c6aabf0b0325e69d66badb))

The home page status line, the edit dialog, the help screen, and the readme say that a terminal
  pastes with Ctrl+Shift+V, not Ctrl+V. Screenshots are refreshed.

Closes #40

### Refactoring

- **tui**: Remove the command palette and the theme picker
  ([`482aa19`](https://github.com/kraigochieng/claude-code-env-editor/commit/482aa199f4e6dd391b65ac8f184773bfa0f6dd74))

Set ENABLE_COMMAND_PALETTE to False. Ctrl+P does nothing and the footer has no palette entry. Rename
  theme.tcss to styles.tcss, since it holds the fixed look of the tool and not a theme.

Closes #42

### Testing

- Add opt-in live tests against real providers
  ([`8c4cf77`](https://github.com/kraigochieng/claude-code-env-editor/commit/8c4cf779a64543696113667e3d9a64a453943b81))

The tests send max_tokens=1 requests to DeepSeek and OpenRouter. They run only with -m live and when
  the key variables are set. They skip on a network error. CI does not run them.

Closes #36


## v0.5.0 (2026-10-10)

### Features

- **envvars**: Make the effort level a choice and range-check the compact window
  ([`9a05e4a`](https://github.com/kraigochieng/claude-code-env-editor/commit/9a05e4a0f52eca609c3985f901650bac08f72afd))

Refs #34

- **tui**: Edit a choice variable from a list
  ([`7dd26de`](https://github.com/kraigochieng/claude-code-env-editor/commit/7dd26dec67707e5da8c5043da60ae3a4716a22ac))

The vars command lists the allowed values and the range.

Closes #34

- **verify**: Show clear messages for failed checks
  ([`66f0c0f`](https://github.com/kraigochieng/claude-code-env-editor/commit/66f0c0f88364703deda3f532c8b23ae480d851d3))

Show the provider error message instead of raw JSON, suggest close model names from the models list,
  explain a rejected key after a public models list, and give plain reasons for 402, 429, 5xx,
  timeouts, and connection errors. Name the model that was sent when a suffix is removed.

Closes #32


## v0.4.0 (2026-10-10)

### Bug Fixes

- **verify**: Send both auth headers when both variables are set
  ([`ab04bc4`](https://github.com/kraigochieng/claude-code-env-editor/commit/ab04bc4c8139e3dbdd44c1478651fca524108c92))

Claude Code sends Authorization and x-api-key together when ANTHROPIC_AUTH_TOKEN and
  ANTHROPIC_API_KEY are both set. I tested this with a fake local server. Verify now does the same.

Closes #28

### Documentation

- Explain which key variable to set and refresh screenshots
  ([`b02e190`](https://github.com/kraigochieng/claude-code-env-editor/commit/b02e19048737daecb0abee76ff12b35f2f92b1b9))

Closes #30

### Features

- **presets**: Record the auth variable that each preset expects
  ([`9480cea`](https://github.com/kraigochieng/claude-code-env-editor/commit/9480cea02c83ffe7fd11d3ed9c52bee16692633d))

Refs #30

- **tui**: Show only the auth variable that matches the base url
  ([`1b498d3`](https://github.com/kraigochieng/claude-code-env-editor/commit/1b498d39f41bca27813c3af6ae86927caa5ef088))

The unused secret variable is hidden when it has no value. A set variable stays visible with a
  warning in the banner. An unknown endpoint shows both variables. The show command does the same.

Refs #30

### Testing

- Name the arguments in the login tests
  ([`ce757c0`](https://github.com/kraigochieng/claude-code-env-editor/commit/ce757c006412eefcd6d677ed009b06bbb466c864))

Refs #30


## v0.3.2 (2026-10-10)

### Bug Fixes

- **verify**: Skip the key check when a claude login is used
  ([`a0c2aea`](https://github.com/kraigochieng/claude-code-env-editor/commit/a0c2aeacc77def7da3412652f0b6c943afd32a57))

Without a key, verify no longer fails on the Anthropic API. It skips the key check and says whether
  a login was found. A local endpoint gets an unauthenticated request. A remote custom endpoint
  still fails. The tool checks only that the oauthAccount key exists. It never reads the login data.

Closes #26

### Continuous Integration

- Lint with ruff
  ([`f7f56d2`](https://github.com/kraigochieng/claude-code-env-editor/commit/f7f56d29c98365ea4c53e30fcd487bab6a509723))

Check unused names, import order, and function types in CI.

Closes #21

### Documentation

- Add screenshots of the tui pages to the readme
  ([`ba40388`](https://github.com/kraigochieng/claude-code-env-editor/commit/ba40388066e5c469d731b7419a01d055bb71d453))

Closes #24

### Refactoring

- Add a type hint to every variable in src
  ([`fbf5b58`](https://github.com/kraigochieng/claude-code-env-editor/commit/fbf5b58f3274caf621c1bde87df8134f7d48765d))

Module constants use Final. Pydantic model_config and the Textual BINDINGS use ClassVar. Imports are
  sorted and unused ones are removed.

Refs #19

### Testing

- Add a type hint to every variable in tests
  ([`5a300ee`](https://github.com/kraigochieng/claude-code-env-editor/commit/5a300ee89f775a9da3f8916e0ab2979c9e88f837))

Closes #19


## v0.3.1 (2026-10-10)

### Bug Fixes

- **ci**: Check types with the python version that runs mypy
  ([`2e3daf7`](https://github.com/kraigochieng/claude-code-env-editor/commit/2e3daf7f2b6396fa153169264cf7d4ccf51fd7cc))

A pinned python_version made mypy look for tomli on Python 3.12.

Refs #17

### Continuous Integration

- Check types with mypy in strict mode
  ([`cd266d5`](https://github.com/kraigochieng/claude-code-env-editor/commit/cd266d5ded1e37e6d1a4e66f1a82e149a72ad22c))

Closes #17

### Refactoring

- Add explicit type hints to all functions in src
  ([`0143b5e`](https://github.com/kraigochieng/claude-code-env-editor/commit/0143b5e385f4382f5b4801fdd7aff8f7e30b67ab))

Final constants, a typed Namespace for the command handlers, and the App type argument remove the
  last implicit types.

Refs #17

- Name the arguments in function calls
  ([`d923372`](https://github.com/kraigochieng/claude-code-env-editor/commit/d9233728a9f416a0a4916c37d9d7346bc123b19a))

Calls to project functions and to library functions that accept keywords now use named arguments.
  Positional-only built-ins and *args parameters stay as they were.

Refs #15

- **config**: Read and write settings.json through a pydantic Settings model
  ([`13428d7`](https://github.com/kraigochieng/claude-code-env-editor/commit/13428d743989a5fe89cdfb0a4b7ebf25904f9581))

Refs #13

- **envvars**: Use pydantic models for VarSpec and Row
  ([`532ca24`](https://github.com/kraigochieng/claude-code-env-editor/commit/532ca24df0c6a982c63ea52e9030a1736cb29aa2))

Refs #13

- **presets**: Load presets as pydantic Preset models
  ([`b069e47`](https://github.com/kraigochieng/claude-code-env-editor/commit/b069e47d47d7c3438bb5acb75969ea1e8cc03398))

Refs #13

- **registry**: Read dirs.toml through a pydantic model
  ([`7c95a2a`](https://github.com/kraigochieng/claude-code-env-editor/commit/7c95a2a48df30d4d9811b4cfb6673968940b9bf2))

Refs #13

- **verify**: Model checks and the endpoint with pydantic
  ([`ab5f789`](https://github.com/kraigochieng/claude-code-env-editor/commit/ab5f7893f958b08c9479f03065e72b15d5208909))

Closes #13

### Testing

- Add type hints to all test functions and helpers
  ([`c90a1fa`](https://github.com/kraigochieng/claude-code-env-editor/commit/c90a1fa4f3f7ca64475e437e8cef987cbfd89bf8))

Refs #17


## v0.3.0 (2026-10-10)

### Documentation

- Add docstrings to all functions and classes
  ([`c3fd357`](https://github.com/kraigochieng/claude-code-env-editor/commit/c3fd357d36b057613be1ea0a3617ffbcb77aa376))

Refs #9

- Add example for several claude code logins
  ([`10947b0`](https://github.com/kraigochieng/claude-code-env-editor/commit/10947b008f7b08a0abbfd0f8d175b0d47dca6a78))

Refs #7

### Features

- **cli**: Add dirs command to list, add, and remove config directories
  ([`012a715`](https://github.com/kraigochieng/claude-code-env-editor/commit/012a715ae6e3e7e61dfcc7ca38ce76943a24938c))

Closes #11

- **config**: Find config directories by content, not by name
  ([`f9c6a6f`](https://github.com/kraigochieng/claude-code-env-editor/commit/f9c6a6f7a8bff4e0b76594f12d14e4f152862d41))

Refs #11

- **registry**: Keep a list of config directories in the os config dir
  ([`682ede3`](https://github.com/kraigochieng/claude-code-env-editor/commit/682ede358cf514d7fae7d8504530c6e18acb894a))

Refs #11

### Refactoring

- Rename vague helper names to descriptive names
  ([`23ec166`](https://github.com/kraigochieng/claude-code-env-editor/commit/23ec166ade7e572ba3c654ca8b00dd909aa6957b))


## v0.2.0 (2026-10-10)

### Refactoring

- Remove the secret store
  ([`2e5c573`](https://github.com/kraigochieng/claude-code-env-editor/commit/2e5c5734e1f2534997ccbe46d392ebca8fab2f9b))

A secret now goes only to settings.json (mode 0600). The keyring and vault copy was never read by
  Claude Code. --no-write-secret now prints an export line and writes nothing.

BREAKING CHANGE: the keyring and encrypted vault are removed, and --no-write-secret no longer saves
  a copy.

Refs #5

- Use absolute imports
  ([`6a6f212`](https://github.com/kraigochieng/claude-code-env-editor/commit/6a6f21281ecfe962add77f0ee89d24a555c5ccad))

Refs #3

### Breaking Changes

- The keyring and encrypted vault are removed, and


## v0.1.0 (2026-10-10)

### Chores

- Add pyproject and MIT license
  ([`3cb27bb`](https://github.com/kraigochieng/claude-code-env-editor/commit/3cb27bb561f6501221fe175bc2aa5dc144e50eda))

Refs #1

- Initialize repository
  ([`c11faf7`](https://github.com/kraigochieng/claude-code-env-editor/commit/c11faf770e440422f0b4e0ee071884045d35e885))

### Continuous Integration

- Add test, commit check, and release workflows
  ([`04e639b`](https://github.com/kraigochieng/claude-code-env-editor/commit/04e639b7b2c983f348e085cc4133163a2c596c6d))

Refs #1

### Documentation

- Add readme
  ([`a6591bb`](https://github.com/kraigochieng/claude-code-env-editor/commit/a6591bb327bb8f21a75491b5c366804bd6ec1420))

### Features

- **cli**: Add self-update and self-uninstall commands
  ([`bbf21c8`](https://github.com/kraigochieng/claude-code-env-editor/commit/bbf21c8f06b176d38f4de22017ad1b82d653601e))

Refs #1

- **cli**: Add show, set, preset, verify, export, vars, and help commands
  ([`c5ce15e`](https://github.com/kraigochieng/claude-code-env-editor/commit/c5ce15e9eb761fc2be19e3f110630eb3f256e218))

Refs #1

- **config**: Read and write settings.json env block
  ([`84c1673`](https://github.com/kraigochieng/claude-code-env-editor/commit/84c1673bede5da3b39cdcf0b042e46427f418a45))

The write is atomic, keeps a .bak copy, and sets mode 0600.

Refs #1

- **envvars**: Add variable catalog with masking and source lookup
  ([`9453427`](https://github.com/kraigochieng/claude-code-env-editor/commit/94534270afd1c38c7de640c17e5a4fc2f825e5c2))

Refs #1

- **install**: Add curl installer with version selection
  ([`fec9a50`](https://github.com/kraigochieng/claude-code-env-editor/commit/fec9a508ae1805ddd8d2a087094e3da54c199da1))

The script installs the latest release, or the version set with --version. It checks the SHA-256 of
  the wheel before it installs.

Refs #1

- **presets**: Add built-in sample endpoints
  ([`fd95f7f`](https://github.com/kraigochieng/claude-code-env-editor/commit/fd95f7fdf2cd3efafa324a0446cfc979a02c5125))

Refs #1

- **secrets**: Store secrets in os keyring with encrypted fallback
  ([`4c0ee37`](https://github.com/kraigochieng/claude-code-env-editor/commit/4c0ee375824108f0d4ce13e5b65904059a56219b))

Refs #1

- **tui**: Add home, edit, preset, verify, and help screens
  ([`c376073`](https://github.com/kraigochieng/claude-code-env-editor/commit/c37607310abdba6fc17172e5f4237736618064cd))

Refs #1

- **verify**: Check endpoint, key, and model
  ([`5ba3f0c`](https://github.com/kraigochieng/claude-code-env-editor/commit/5ba3f0c77dbb05091042a05964acc89fb8df48df))

Refs #1
