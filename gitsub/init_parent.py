import sys
import os
import toml
import subprocess as sp

from typing import Generator, List

from . import err
from .lib import Child, Remote, CACHEDIR


def _get_remote_locations(root_absolute: str) -> List[Remote]:
    """
    Gather all registered remote locations for a git repo.
    """
    r = sp.run(
        ['git', 'remote', '-v'],
        cwd=root_absolute,
        stdout=sp.PIPE,
    )

    out = r.stdout.decode('utf8')

    remotes = []

    if out:
        for line in out.splitlines():
            if line[-8:] == ' (fetch)':

                remote_str = line[:-8]
                remote_split = remote_str.split('\t')

                remote_name = remote_split[0]
                remote_url = remote_split[1]

                split_url = remote_url.replace(':', '/').split('/')
                remote_host = split_url[-3]
                remote_user = split_url[-2]
                remote_repo_name = split_url[-1]

                root = f'{CACHEDIR}/{remote_host}/{remote_user}/{remote_repo_name}'

                remote = Remote(
                    name=remote_name,
                    url=remote_url,
                    is_ssh=remote_url.startswith('http') == False,
                    cache_root_absolute=root,
                )

                remotes.append(remote)

    if len(remotes) < 1:
        err.print(
            f"Error: Cannot find remote (fetch) location for child git repo: {root_absolute}\n\n"\
            "Please add a remote (fetch) location to the given child git repo. "
            "Remote locations can be added via 'git remote add <shortname> <url>'."
        )
        sys.exit(1)

    return remotes


def _get_current_branch(repo_root: str) -> str:
    """
    Return the currently active branch for a git repo.
    """
    cmd = ['git', 'branch', '--show-current']
    r = sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)
    branch = r.stdout.decode('utf8').replace('\n', '')

    return branch or ''


def _get_current_commit(repo_root: str) -> str:
    """
    Return the currently active commit hash for a git repo.
    """
    cmd = ['git', 'rev-parse', '--verify', 'HEAD']
    r = sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)
    commit = r.stdout.decode('utf8').replace('\n', '')

    if not commit:
        err.print("\nError: Cannot read commit revision for the repo at: " + repo_root)
        sys.exit(1)

    return commit or ''


def _load_child_from_fs(
    parent_root: str,
    child_root_relative: str,
) -> Child:
    """
    """
    child_root_absolute = f"{parent_root}/{child_root_relative}"
    remotes = _get_remote_locations(child_root_absolute)

    return Child(
        current_branch=_get_current_branch(child_root_absolute),
        current_commit=_get_current_commit(child_root_absolute),
        remotes=remotes,
        root_absolute=child_root_absolute,
        root_relative=child_root_relative,
    )


def _load_children_from_fs(
    parent_root: str,
    children_locations: List[str],
) -> Generator[Child, None, None]:
    """
    We read the git repo state from the file system for each child.
    """
    for child_root_relative in children_locations:
        yield _load_child_from_fs(parent_root, child_root_relative)


def _lock_child(parent_root: str, child: Child) -> None:
    """
    Save gathered child data in `parent/.gitsub` (toml).
    """
    with open(f"{parent_root}/.gitsub", 'r') as f:
        lock_data = toml.loads(f.read())

    if not lock_data.get('children'):
        lock_data['children'] = []

    updated_child_data = {
        'root_relative': child.root_relative,
        'branch': child.current_branch,
        'commit': child.current_commit,
        'remotes': [{
            'name': r.name,
            'url': r.url,
        } for r in child.remotes],
    }

    indexes = [
        i for i, c in enumerate(lock_data['children'])
        if c.get('root_relative') == child.root_relative
    ]

    if len(indexes) > 1:
        for i in indexes[1:]:
            lock_data['children'].pop(i)

    if len(indexes) == 0:
        lock_data['children'].append(updated_child_data)
    else:
        lock_data['children'][indexes[0]] = updated_child_data

    with open(f"{parent_root}/.gitsub", 'w') as f:
        f.write(toml.dumps(lock_data))


def _lock_children(parent_root: str, children: List[Child]):
    for child in children:
        _lock_child(parent_root, child)


def run(parent_root):
    """
    Initiate a git repository as a gitsub parent repo.

    This creates a .gitsub in the root of the current git repo.
    Then it searches the file system for child repos and locks them into the .gitsub
    file.
    """
    f = f'{parent_root}/.gitsub'

    if os.path.exists(f):
        err.print("This repo already contains a .gitsub file.")
        sys.exit(1)

    children_fs_locations = _search_children_on_fs(parent_root)

    new_children_to_lock = []

    for child_root_relative in children_fs_locations:
        new_children_to_lock.append(
            _load_child_from_fs(parent_root, child_root_relative)
        )

    open(f, 'a').close()
    print(f'Created: {f}\n')

    for child in new_children_to_lock:
        _lock_child(parent_root, child)
        print("New child repo added to '.gitsub': ", child_root_relative)
