import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_git = shutil.which("git")
if _git is None:
    raise RuntimeError("ERROR: Git is required but was not found in PATH.")

GIT: str = _git


@dataclass(frozen=True)
class Repository:
    root: Path

    def _run(self, *args: str, capture_output: bool = False) -> str:
        result = subprocess.run(  # noqa: S603
            (GIT, "-C", self.root, *args),
            check=True,
            stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            text=True,
        )
        return result.stdout or ""

    def add(self, path: str | Path) -> None:
        self._run("add", "--", str(path))

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def reset(self) -> None:
        self._run("reset", "--hard", "HEAD")

    def staged_count(self) -> int:
        output = self._run(
            "diff", "--cached", "--name-only", "-z", capture_output=True
        )
        return len([path for path in output.split("\0") if path])


def open_repo(reset: bool = True) -> Repository:
    result = subprocess.run(  # noqa: S603
        (GIT, "rev-parse", "--show-toplevel"),
        check=True,
        capture_output=True,
        text=True,
    )
    repo = Repository(Path(result.stdout.strip()))
    if reset:
        repo.reset()

    return repo
