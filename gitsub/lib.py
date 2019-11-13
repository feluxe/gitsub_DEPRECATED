import os
import sys
import toml
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, Future
import subprocess as sp
import requests
from sty import fg
from glob import iglob

from typing import List, Generator

from . import err

CACHEDIR = os.path.expanduser('~/.cache/gitsub')
TEMPDIR = '/tmp/tmp_gitsub'


@dataclass
class Remote:
    name: str
    url: str
    is_ssh: bool
    cache_root_absolute: str


@dataclass
class Child:
    current_branch: str
    current_commit: str
    remotes: List[Remote]
    root_relative: str
    root_absolute: str


def load_locked_children(parent_root: str) -> List[Child]:
    """
    Load .gitsube file and convert toml items into python types.
    """
    gitsub_file = f"{parent_root}/.gitsub"

    with open(gitsub_file, 'r') as f:
        gitsub_data = toml.loads(f.read())

    if not gitsub_data.get('children'):
        gitsub_data['children'] = []

    locked_children = []

    for child in gitsub_data['children']:

        remotes = []

        for remote in child['remotes']:

            split_url = remote['url'].replace(':', '/').split('/')
            remote_host = split_url[-3]
            remote_user = split_url[-2]
            remote_repo_name = split_url[-1]

            root = f'{CACHEDIR}/{remote_host}/{remote_user}/{remote_repo_name}'

            remotes.append(
                Remote(
                    name=remote['name'],
                    url=remote['url'],
                    is_ssh=remote['url'].startswith('http') == False,
                    cache_root_absolute=root
                )
            )

        locked_children.append(
            Child(
                current_branch=child['branch'],
                current_commit=child['commit'],
                remotes=remotes,
                root_relative=child['root_relative'],
                root_absolute=f"{parent_root}/{child['root_relative']}",
            )
        )

    return locked_children


def rename_git_dir(repo_root, from_='', to=''):
    """
    Simply rename `myrepo/.git` <> `myrepo/.gitsub_hidden`. (back and forth).
    """
    src = f'{repo_root}/{from_}'
    dst = f'{repo_root}/{to}'

    if os.path.exists(src):
        os.rename(src, dst)


def search_children_on_fs(parent_root: str) -> Generator[str, None, None]:
    """
    Search the parent repo directory for child .git directories.
    """
    for git_dir_path in iglob(f'{parent_root}/**/.git*', recursive=True):

        # Skip the parent repo.
        if git_dir_path == f'{parent_root}/.git':
            continue

        if git_dir_path.split('.')[-1] not in ['git', 'gitsub_hidden']:
            continue

        if os.path.isfile(git_dir_path):
            continue

        child_root_absolute = git_dir_path\
            .replace('/.gitsub_hidden', '')\
            .replace('/.git', '')

        if '.gitsub_hidden' in git_dir_path:
            rename_git_dir(child_root_absolute, '.gitsub_hidden', '.git')

        child_root_relative = child_root_absolute.replace(parent_root + '/', '')

        yield child_root_relative


def sync_children():

    # Load all children from lock
    # Search and load every child on disk
    # missing_in_fs = Check if child is missing on disk
    # missing_in_lock = Check if child is missing from lock
    #
    # if len(missing_in_fs) > 0:
    #   Ask to download
    # if len(missing_in_lock) > 0:
    #   Ask to add to lock
    pass


def _has_child_changed(
    parent_root: str,
    child: Child,
) -> bool:
    """
    Check if the parent repo finds changes for a child.
    If the files of a child haven't changed on a parent, there is no need to
    run any further check.
    """
    cmd = ['git', 'status', '-s', child.root_relative]
    r = sp.run(cmd, cwd=parent_root, stdout=sp.PIPE)
    out = r.stdout.decode('utf8').replace('\n', '')

    if out:
        return True
    else:
        return False


def _has_child_unpushed_changes(parent_root: str, child: Child):
    """
    Check if the child repo itself has unpushed changes.
    """

    cmd = ['git', 'status', '-s']
    r = sp.run(cmd, cwd=child.root_absolute, stdout=sp.PIPE)
    changes = r.stdout.decode('utf8').replace('\n', '')

    if changes != '':
        err.print(f"\nUnstaged Changes in: {child.root_relative}")
        return True
    else:
        return False


def _commit_exists(repo_root, commit):
    """
    Check if a commit hash exists in a git repo.
    """

    cmd = ['git', 'cat-file', '-t', commit]
    r = sp.run(cmd, cwd=repo_root, stdout=sp.PIPE, stderr=sp.PIPE)
    out = r.stdout.decode('utf8').replace('\n', '')

    if out == 'commit':
        return True
    else:
        return False


def _child_commit_exist_at_remote(parent_root, child: Child):
    """
    Check if a commit exists in a remote repository.
    This clones/fetches the remote repo into a cache dir and checks for the
    commit in there.
    """
    for remote in child.remotes:
        if not os.path.exists(remote.cache_root_absolute):
            print(
                f"{fg.li_black}Gitsub: Clone repo into cache-dir for: {child.root_relative}{fg.rs} "
            )
            cmd = ['git', 'clone', remote.url, remote.cache_root_absolute]
            sp.run(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

        print(
            f"{fg.li_black}Gitsub: Update cached remote-repo for: {child.root_relative}{fg.rs}"
        )

        if remote.is_ssh == True:
            cmd = ['git', 'remote', 'set-url', 'origin', remote.url]
            sp.run(cmd, stdout=sp.PIPE, cwd=remote.cache_root_absolute)

        sp.run(
            ['git', 'fetch', 'origin', child.current_branch],
            cwd=remote.cache_root_absolute,
            stdout=sp.PIPE,
            stderr=sp.PIPE
        )

        if not _commit_exists(remote.cache_root_absolute, child.current_commit):
            sys.stderr.write(
                f"\n    Current commit cannot be found on remote for: {child.root_relative}\n"
            )
            return False
        else:
            return True


def validate_children(
    parent_root: str,
    locked_children: List[Child],
    fs_children: Generator[Child, None, None],
) -> None:
    """
    Check if children are good enough for the parent to commit their files.
    """
    all_children = []  # gather children from the generator here for later use.

    with ProcessPoolExecutor() as executor:

        # Check1 (in parallel): Has child repo changes at all?

        futures = []

        for child in fs_children:
            all_children.append(child)
            f: Future = executor.submit(_has_child_changed, parent_root, child)
            futures.append((f, child))

        children_filtered = [child for f, child in futures if f.result() == True]

        # Check2 (in parallel): Has child-repo unpushed changes?

        futures = []

        for child in children_filtered:
            f = executor.submit(_has_child_unpushed_changes, parent_root, child)
            futures.append((f, child))

        if any([f.result() for f, child in futures]):
            err.print_msg_unstaged()
            sys.exit(1)

        futures = []

        for child in children_filtered:
            f = executor.submit(requests.get, child.remotes[0].url)
            futures.append((f, child))

        # Gather children that require no remote authentication for 'check3'(in parallel).
        # This only happens if there are more than 2 filtered children left.

        children_parallel = []

        if len(children_filtered) > 2:

            for f, child in futures:
                try:
                    r = f.result()
                    if r.status_code == 200:
                        children_parallel.append(child)
                except requests.exceptions.InvalidSchema:
                    pass

            # Check3 (in parrallel): Check if current commit exists in remote repo?
            # This is for repos that require no login data from the user.

            futures = []
            for child in children_parallel:
                f = executor.submit(_child_commit_exist_at_remote, parent_root, child)
                futures.append((f, child))

            if not all([f.result() for f, child in futures]):
                err.print_msg_unstaged()
                sys.exit(1)

        # Check3 (sequential): This is for repos that require login data from he user.

        children_sequential = [
            c for c in children_filtered if c not in children_parallel
        ]

        for child in children_sequential:
            if not _child_commit_exist_at_remote(parent_root, child):
                err.print_msg_unstaged()
                sys.exit(1)

    # Check if all children exist in file system

    if len(locked_children) != len(all_children):

        locations1 = [c.root_relative for c in locked_children]
        locations2 = [c.root_relative for c in all_children]
        missing = [l for l in locations1 if l not in set(locations2)]

        err.print_child_git_repo_missing(missing)
        sys.exit(1)
