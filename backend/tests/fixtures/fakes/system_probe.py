"""A Mac described by plain values. Fake of the SystemProbe port."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FakeSystemProbe:
    """Answers from the values a test gives it. The defaults describe a healthy Mac."""

    macos: str = "15.6.1"
    architecture: str = "arm64"
    python: str = "3.14.10"
    commands: dict[str, str] = field(default_factory=dict[str, str])
    modules: set[str] = field(default_factory=set[str])
    packages: dict[str, str] = field(default_factory=dict[str, str])
    files: set[Path] = field(default_factory=set[Path])
    writable: bool = True
    free: int = 50 * 1024**3

    def os_version(self) -> str:
        """Return the configured macOS version."""
        return self.macos

    def cpu_architecture(self) -> str:
        """Return the configured architecture."""
        return self.architecture

    def python_version(self) -> str:
        """Return the configured Python version."""
        return self.python

    def command_version(self, command: str) -> str | None:
        """Return the version line of a configured command, or None."""
        return self.commands.get(command)

    def module_available(self, name: str) -> bool:
        """Return whether the module was configured as present."""
        return name in self.modules

    def package_version(self, name: str) -> str | None:
        """Return the version of a configured package, or None."""
        return self.packages.get(name)

    def file_exists(self, path: Path) -> bool:
        """Return whether the file was configured as present."""
        return path in self.files

    def can_write_to(self, folder: Path) -> bool:
        """Return the configured answer."""
        return self.writable

    def free_bytes(self, folder: Path) -> int:
        """Return the configured free space."""
        return self.free
