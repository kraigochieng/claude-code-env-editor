# claude-code-env-editor

A terminal UI to view, edit, and verify the Anthropic variables that Claude Code reads.
Point Claude Code at another endpoint without hand-editing JSON or shell files.

## Install

```sh
curl -LsSf https://raw.githubusercontent.com/kraigochieng/claude-code-env-editor/main/install.sh | sh
```

Install a chosen version:

```sh
curl -LsSf https://raw.githubusercontent.com/kraigochieng/claude-code-env-editor/main/install.sh | sh -s -- --version 0.2.0
```

Read [install.sh](install.sh) before you run it. It installs `uv` if needed, checks the SHA-256 of the
release wheel, then runs `uv tool install`. Linux and macOS are supported. On Windows use WSL.

Update: `claude-code-env-editor self-update [--version X.Y.Z]`. Remove: `claude-code-env-editor self-uninstall`.

## Use

```sh
claude-code-env-editor          # open the TUI
claude-code-env-editor show     # print variables, values, and sources
claude-code-env-editor preset deepseek
claude-code-env-editor set ANTHROPIC_AUTH_TOKEN      # asks for the secret
claude-code-env-editor verify
claude-code-env-editor export   # 'export NAME=value' lines
claude-code-env-editor help set
```

`cce` is a short alias. Inside the TUI press `?` for the key list.

| Key | Action |
|---|---|
| `e` / `enter` | Edit the selected variable |
| `v` | Verify the endpoint, the key, and the model |
| `r` | Reveal or hide secrets |
| `p` | Apply a preset |
| `d` | Switch config directory |
| `x` | Remove the variable |
| `?` | Help |
| `q` | Quit |

## Variables

Run `claude-code-env-editor vars` for the full list: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`,
`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`,
`CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_EFFORT_LEVEL`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`,
`ANTHROPIC_SMALL_FAST_MODEL`, `API_TIMEOUT_MS`, `CLAUDE_CONFIG_DIR`.
Other `ANTHROPIC_*` and `CLAUDE_CODE_*` keys in `settings.json` show as custom rows and are kept.

The tool reads two sources. The process environment wins over the `env` block of `settings.json`.
It writes only the `env` block. All other keys in the file stay as they were.

## Presets

`claude-code-env-editor preset` lists them: Anthropic, OpenRouter, Z.ai, Moonshot, DeepSeek,
LiteLLM, Ollama. **Check each URL and model name before you rely on it. Providers change them.**
The DeepSeek preset sets the base URL, all model aliases, the subagent model, the effort level, and the
compact window. It never sets a key.

## Several Claude Code logins

Each login lives in its own config directory. `CLAUDE_CONFIG_DIR` selects it, and each directory has its
own `settings.json` and its own `env` block. So each login can have its own endpoint.

```sh
claude-code-env-editor --config-dir ~/.claude-work show     # per command
alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'
```

Inside the TUI press `d` to switch between the `~/.claude*` directories.

## Security

- Secrets (`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`) show masked. The tool never logs them.
- `settings.json` is written atomically with mode `0600`. The old file stays as `settings.json.bak`.
- Claude Code reads keys from `settings.json` or the environment, so that is where the tool writes them.
  The tool keeps no second copy. Any program that runs as you can read the file. Keep the file private.
  Use `set --no-write-secret` to keep a key out of the file. The tool prints an `export` line instead.
- Verify sends requests only to your `ANTHROPIC_BASE_URL`, shows the host first, and never follows a
  redirect. It warns about `http://` URLs that are not local.
- Secrets are never read from command arguments, so they stay out of shell history.

## Verify

Verify runs three checks: the URL, `GET /v1/models` (proves the key), and a one-token
`POST /v1/messages` (proves the model name). A `[1m]` suffix is removed from the model name before the request.
A `404` on `/v1/models` is shown as `skip`, because some providers have no such route.

## Versions

Versions follow [Semantic Versioning](https://semver.org) and are computed from
[Conventional Commits](https://www.conventionalcommits.org). A change to the settings file handling that
breaks existing files is a breaking change. See the [releases](https://github.com/kraigochieng/claude-code-env-editor/releases).

## Develop

```sh
uv venv && uv pip install -e '.[dev]'
.venv/bin/python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
