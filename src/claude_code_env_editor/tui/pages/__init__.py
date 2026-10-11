"""The two main pages: the profile list, and the variables of one profile."""

from claude_code_env_editor.tui.pages.base import BasePage
from claude_code_env_editor.tui.pages.profile_list import ProfileListPage
from claude_code_env_editor.tui.pages.table import PageTable
from claude_code_env_editor.tui.pages.variables import VariablesPage

__all__ = ["BasePage", "PageTable", "ProfileListPage", "VariablesPage"]
