"""Where the variables page reads and writes its values: one profile."""

from __future__ import annotations

from collections.abc import Mapping

from claude_code_env_editor.profiles import Profile, save_profile


class ProfileSource:
    """The variables of one profile. A change goes to profiles.toml."""

    def __init__(self, profile: Profile) -> None:
        """Keep the profile."""
        self.profile: Profile = profile
        self.name: str = profile.name

    def load(self) -> dict[str, str]:
        """Return the variables of the profile."""
        return dict(self.profile.variables)

    def save(self, updates: Mapping[str, str | None]) -> None:
        """Write the changed profile to profiles.toml. An invalid value raises ValueError."""
        variables: dict[str, str] = dict(self.profile.variables)
        for key, value in updates.items():
            if value is None:
                variables.pop(key, None)
            else:
                variables[key] = value
        changed: Profile = Profile(name=self.profile.name, variables=variables, note=self.profile.note)
        save_profile(profile=changed, overwrite=True)
        self.profile = changed
