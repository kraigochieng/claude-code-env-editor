"""View, edit, and verify Anthropic variables for Claude Code."""

try:
    from ._version import __version__
except ImportError:  # running from a source tree without a build
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
