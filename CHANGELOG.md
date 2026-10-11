# CHANGELOG


## v0.16.0 (2026-10-11)

### Features

- **tui**: Keep actions on the profile list, edit the name, style key hints, close on outside click
  ([`b766244`](https://github.com/kraigochieng/claude-code-env-editor/commit/b766244b09f32ec10245fd38bbc215c2d7181baa))

Apply, merge, copy, and verify are keys and instructions of the profile list only. The profile page
  has edit, remove, back, help, and quit. The list has c to copy and e to edit the name, and r is
  gone. The keys in the hint lines of every dialog and in the help use the colour of the footer
  keys. A click outside a dialog closes it like Esc, and a confirm dialog answers no. README and
  screenshots follow.

Closes #70


## v0.15.0 (2026-10-11)

### Features

- **profiles**: Refuse a name that differs from another only in case
  ([`6c795d4`](https://github.com/kraigochieng/claude-code-env-editor/commit/6c795d40254a2207441bdf0dc52fc12ea59baecd))

Work and work would be two profiles that look the same. save and rename now refuse such a name. A
  profile may still change the case of its own name.

Refs #68

- **tui**: Simplify the pages and create a profile from scratch with n
  ([`39be977`](https://github.com/kraigochieng/claude-code-env-editor/commit/39be9774f4f259a7da1cbcea0b6e65e388ddf573))

n asks for a name, creates an empty profile, and opens it. The right arrow opens a profile and the
  left arrow goes back. The Applied in and Note columns, the Source column, and the endpoint and
  auth lines of the profile page are gone. The reveal control moves into the edit box of a key
  (Ctrl+R), so r is no longer a key of the pages. The template, folder, and copy flows of n are
  removed from the TUI. The CLI keeps them. Names are checked without case in every box. README and
  screenshots follow.

Closes #68


## v0.14.0 (2026-10-11)

### Features

- **tui**: Apply a profile to a place you choose and drop the target state
  ([`988e1d8`](https://github.com/kraigochieng/claude-code-env-editor/commit/988e1d823ac0327d204b3f4a381ca5134bf8bfc6))

a and m list your login folders, with the state of the profile in each, and a project folder (its
  .claude/settings.local.json). A dialog then lists every change. The pages no longer show a file or
  a config directory, and the d, c, and s keys are gone. Verify tests the endpoint of the profile
  under the cursor. --config-dir and --file only put a place first in the list. FileSource and
  matching_profile are removed. README and screenshots follow the new flow.

Closes #66


## v0.13.0 (2026-10-11)

### Features

- **tui**: Show where each profile is applied and add a new profile flow
  ([`d1cacda`](https://github.com/kraigochieng/claude-code-env-editor/commit/d1cacdadfacc711035e198c3b4be9b197872b045))

The profile list has an Applied in column with the login folders whose file matches the profile. n
  creates a profile from a template, from the values of a folder (a login, or a project folder's
  .claude/settings.local.json), or as a copy of a profile. The key question shows when imported
  values hold a key.

Closes #64


## v0.12.0 (2026-10-11)

### Features

- **destinations**: Model the places where a profile is applied
  ([`24fb495`](https://github.com/kraigochieng/claude-code-env-editor/commit/24fb4957ffe8f492f95edbb7f54898de199715ae))

A Destination is one settings file: a login (a config directory) or a project folder
  (.claude/settings.local.json). destination_state tells if a profile matches, differs, or if the
  place is empty or unreadable. applied_in maps each profile to the places whose file matches it.
  The screens do not change yet.

Closes #62


## v0.11.0 (2026-10-11)

### Features

- **profiles**: Make the templates normal profiles and add rename
  ([`4e21962`](https://github.com/kraigochieng/claude-code-env-editor/commit/4e2196275e38f4e5f27032fdf83e41997137eb1e))

The templates are copied into profiles.toml on first use, and once for a file from an older version,
  under names that are free. A marker stops a second copy, so a profile that you delete stays
  deleted. Every profile can be edited, renamed, and deleted. The built-in flag, the read-only rule,
  and the Kind column are removed.

profile rename OLD NEW renames a profile and keeps its position, its variables, and its note.
  profile templates lists the templates. save --from and preset accept a template name, also after
  the template was removed from the list. r in the TUI list renames the profile under the cursor.
  README describes templates.

Closes #60


## v0.10.0 (2026-10-11)

### Documentation

- Describe profiles as the way to switch provider and refresh screenshots
  ([`f8f9e9d`](https://github.com/kraigochieng/claude-code-env-editor/commit/f8f9e9dd602340234abea505df5112d9beedabe8))

The README now leads with profiles, names the built-in ones, and says that a profile can hold a copy
  of the key. The screenshots show the profile list and the apply dialog. The old preset page is
  removed.

Closes #56

### Features

- **sources**: Add variable sources and profile matching
  ([`143b301`](https://github.com/kraigochieng/claude-code-env-editor/commit/143b30136d1def97f50e91e2e89ade461c57900e))

A FileSource reads and writes the env block of a settings file. A ProfileSource reads and writes one
  profile, and a built-in is read-only. matching_profile finds the profile that equals the known
  variables of a file.

Refs #58

- **tui**: Make the profile list the main page
  ([`d70f4b1`](https://github.com/kraigochieng/claude-code-env-editor/commit/d70f4b141ad364d3c12c73dabb7c325555479fe1))

The main page lists the profiles with a mark on the one that matches the file, and the banner names
  it. Enter opens a profile and shows its variables. A profile of yours can be edited and is saved
  to profiles.toml. A built-in is read-only and c copies it. c on the list opens the current values
  of the file. The dialogs move to their own module. README and screenshots follow the new layout.

Closes #58


## v0.9.0 (2026-10-11)

### Features

- **apply**: Add a wrapped summary format for narrow dialogs
  ([`4b22b54`](https://github.com/kraigochieng/claude-code-env-editor/commit/4b22b54ffbc5bfe04f6958880fc6c38b2600dab5))

Each change takes up to three short lines: name, value, previous value.

Refs #54

- **tui**: Add a profile page and a settings file target
  ([`2cae87e`](https://github.com/kraigochieng/claude-code-env-editor/commit/2cae87e4856625559f36dfe324053f9bdc582c6b))

p opens the profile list. Enter applies in replace mode and m in merge mode, after a dialog with the
  changes. s saves the current values, with a question about the key. x deletes one of your
  profiles. A key is refused for a file that may be committed. d can open any settings file, and tui
  accepts --file. The confirm text scrolls, so the key hints always show.

Closes #54


## v0.8.0 (2026-10-10)

### Features

- **apply**: Plan what a profile changes in a settings file
  ([`e8025cf`](https://github.com/kraigochieng/claude-code-env-editor/commit/e8025cfc4d2d1cf5882ee1dd2723eae551360b63))

Replace mode removes the known variables that the profile does not list and keeps a key when the
  endpoint host stays the same. Merge mode changes only the listed variables. A key is refused for a
  file that may be committed.

Refs #52

- **cli**: Apply profiles and point commands at any settings file
  ([`9ed999a`](https://github.com/kraigochieng/claude-code-env-editor/commit/9ed999ae7500ab07aab413c7dc6dfde9616b2284))

profile apply shows the changes, asks, and writes. It has --merge, --dry-run, --yes, and
  --allow-secret-in-shared-file. --file PATH works on show, set, unset, preset, verify, export, and
  profile. preset NAME keeps its behavior and runs through the same code.

Closes #52

- **target**: Point a target at any settings file
  ([`737991c`](https://github.com/kraigochieng/claude-code-env-editor/commit/737991cae6369428ea1a9d2d7df2aad17d150792))

from_file marks a settings.json in a known config directory as user level. Any other file, such as a
  project file, uses the default login.

Refs #52


## v0.7.0 (2026-10-10)

### Features

- **cli**: Add the profile command
  ([`f23e1a6`](https://github.com/kraigochieng/claude-code-env-editor/commit/f23e1a685e4e0da2002698c819e86dd1b0ab54e1))

profile lists, shows, saves, and deletes profiles. save takes the values of the target, or copies a
  profile with --from. --no-key leaves the key out. show masks keys unless --reveal is given.

Closes #50

- **profiles**: Store named sets of variables in profiles.toml
  ([`afb2235`](https://github.com/kraigochieng/claude-code-env-editor/commit/afb2235aa3bc98601c1b1847f3cbd63f63afa80c))

A profile holds known variables with valid values, an optional key, and a note. The file has mode
  0600 in a 0700 directory, with a .gitignore. Built-in profiles come from the presets. A broken
  file is never overwritten.

Refs #50

### Refactoring

- Let the config functions take a settings file and add a Target model
  ([`5a6f754`](https://github.com/kraigochieng/claude-code-env-editor/commit/5a6f754480fb7fedcec9dda628621b4810d77695))

load_settings, load_env, and update_env take a settings file. A Target holds that file and the
  config directory whose login applies. The command line and the TUI build a Target from the config
  directory, so behavior does not change. Profiles will point a Target at any file.

Closes #48

- **config**: Write settings files through an atomic write helper
  ([`57ddcfa`](https://github.com/kraigochieng/claude-code-env-editor/commit/57ddcfa09f39b513b19bda6d5d19492b7d1f2f3d))

The helper writes a temporary file, sets the mode, and renames it. It can keep a private .bak copy.
  Profiles will use it for profiles.toml.

Refs #48


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
