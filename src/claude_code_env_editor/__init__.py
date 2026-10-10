"""View, edit, and verify Anthropic variables for Claude Code."""

try:
    from claude_code_env_editor._version import __version__
except ImportError:  # running from a source tree without a build
    __version__ = "0.0.0+unknown"

__all__: list[str] = ["__version__"]
