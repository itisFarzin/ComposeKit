try:
    from git import Repo
except ImportError as err:
    raise RuntimeError(
        "ERROR: Missing required packages. See the README."
    ) from err


def open_repo(reset: bool = True) -> Repo:
    repo = Repo(".", search_parent_directories=True)
    if reset:
        # Discard any changes
        _ = repo.index.reset(working_tree=True)

    return repo
