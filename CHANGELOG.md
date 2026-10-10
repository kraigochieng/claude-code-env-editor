# CHANGELOG


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
