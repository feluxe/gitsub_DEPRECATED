import os
import sys
import toml
import subprocess as sp
from typing import List, Optional, Union, Tuple
from glob import iglob
from dataclasses import dataclass, asdict
from sty import fg
from concurrent.futures import ProcessPoolExecutor
import requests

CACHEDIR = os.path.expanduser('~/.cache/gitsub')

err_msg_unstaged = """
Note: You cannot update a parent repo, as long as it contains subrepos with changes 
that haven't been pushed to their remote locations.
"""


def get_repo_root() -> str:

    cmd = ['git', 'rev-parse', '--show-toplevel']

    r = sp.run(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

    if r.returncode == 128:
        pass
    elif r.returncode == 0:
        pass
    else:
        print(r.stderr)
        sys.exit(1)

    repo_root = r.stdout.decode('utf8').replace('\n', '')

    return repo_root or ''


def is_repo_gitsub(repo_root: str) -> bool:

    if not repo_root:
        return False

    if os.path.isfile(f'{repo_root}/.gitsub'):
        return True
    else:
        return False


@dataclass
class Parent:
    root_absolute: str
    gitsub_file: str
    locked_children: List[dict]


def get_parent_data(repo_root: str) -> Parent:

    gitsub_file = f"{repo_root}/.gitsub"

    with open(gitsub_file, 'r') as f:
        gitsub_data = toml.loads(f.read())

    if not gitsub_data.get('children'):
        gitsub_data['children'] = []

    return Parent(
        root_absolute=repo_root,
        gitsub_file=gitsub_file,
        locked_children=gitsub_data['children'],
    )


@dataclass
class Remote:
    name: str
    url: str
    is_ssh: bool
    cache_root_absolute: str


def get_remote_locations(root_absolute: str) -> List[Remote]:

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
        print(f"Cannot find (fetch) remote for: {root_absolute}")

    return remotes


@dataclass
class Child:
    current_branch: str
    current_commit: str
    remotes: List[Remote]
    root_relative: str
    root_absolute: str


def get_current_branch(repo_root: str) -> str:
    cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
    r = sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)
    branch = r.stdout.decode('utf8').replace('\n', '')

    return branch or ''


def get_current_commit(repo_root: str) -> str:
    cmd = ['git', 'rev-parse', '--verify', 'HEAD']
    r = sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)
    commit = r.stdout.decode('utf8').replace('\n', '')

    return commit or ''


def get_child_data(parent: Parent, root_relative: str) -> Child:

    root_absolute = f'{parent.root_absolute}/{root_relative}'

    remotes = get_remote_locations(root_absolute)

    child = Child(
        current_branch=get_current_branch(root_absolute),
        current_commit=get_current_commit(root_absolute),
        remotes=remotes,
        root_absolute=root_absolute,
        root_relative=root_relative,
    )

    return child


def has_child_changes_in_parent(
    parent: Parent,
    child: Child,
) -> Tuple[bool, Child]:

    cmd = ['git', 'status', '-s', child.root_relative]
    r = sp.run(cmd, cwd=parent.root_absolute, stdout=sp.PIPE)
    out = r.stdout.decode('utf8').replace('\n', '')

    if out:
        return True, child
    else:
        return False, child


def has_child_unpushed_changes(parent: Parent, child: Child):

    cmd = ['git', 'status', '-s']
    r = sp.run(cmd, cwd=child.root_absolute, stdout=sp.PIPE)
    changes = r.stdout.decode('utf8').replace('\n', '')

    if changes != '':
        print(f"\nUnstaged Changes in: {child.root_relative}")
        return True
    else:
        return False


def commit_exists(repo_root, commit):

    cmd = ['git', 'cat-file', '-t', commit]
    r = sp.run(cmd, cwd=repo_root, stdout=sp.PIPE, stderr=sp.PIPE)
    out = r.stdout.decode('utf8').replace('\n', '')

    if out == 'commit':
        return True
    else:
        return False


def check_child_commit_exist_in_remote(parent: Parent, child: Child):

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

        if not commit_exists(remote.cache_root_absolute, child.current_commit):
            print(
                f"\n    Current commit cannot be found on remote for: {child.root_relative}"
            )
            return False
        else:
            return True


def rename_git_dir(repo_root, from_='', to=''):

    src = f'{repo_root}/{from_}'
    dst = f'{repo_root}/{to}'

    if os.path.exists(src):
        os.rename(src, dst)


def update_gitsub_file(parent: Parent, child: Child) -> None:

    with open(parent.gitsub_file, 'r') as f:
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

    with open(parent.gitsub_file, 'w') as f:
        f.write(toml.dumps(lock_data))


def get_children_from_fs(parent):

    for git_dir_path in iglob('**/.git*', recursive=True):

        # Skip the parent repo.
        if git_dir_path == '.git':
            continue

        if git_dir_path.split('.')[-1] not in ['git', 'gitsub_hidden']:
            continue

        if os.path.isfile(git_dir_path):
            continue

        child_root_relative = git_dir_path\
            .replace('/.gitsub_hidden', '')\
            .replace('/.git', '')

        if '.gitsub_hidden' in git_dir_path:
            rename_git_dir(
                repo_root=child_root_relative,
                from_='.gitsub_hidden',
                to='.git',
            )

        child = get_child_data(parent, child_root_relative)

        yield child


def validate_children(parent, children):

    children_filtered = []
    all_children = []  # gather children from the generator here.

    with ProcessPoolExecutor() as executor:

        # If children have not changed on the parent repo, there is no need for
        # further checks. Filter out those who haven't changed on parent.

        futures = []

        for child in children:

            all_children.append(child)

            f = executor.submit(has_child_changes_in_parent, parent, child)
            futures.append(f)

        for f in futures:
            r = f.result()
            if r[0] == True:
                children_filtered.append(r[1])

        futures = []

        for child in children_filtered:
            f = executor.submit(has_child_unpushed_changes, parent, child)
            futures.append(f)

        if any([f.result() for f in futures]):
            print(err_msg_unstaged)
            sys.exit(1)

        futures = []

        for child in children_filtered:
            f = executor.submit(requests.get, child.remotes[0].url)
            futures.append((f, child))

        children_parallel = []

        for f, child in futures:
            try:
                r = f.result()
                if r.status_code == 200:
                    children_parallel.append(child)
            except requests.exceptions.InvalidSchema:
                pass

        futures = []
        for child in children_parallel:
            f = executor.submit(
                check_child_commit_exist_in_remote, parent, child
            )
            futures.append(f)

        if not all([f.result() for f in futures]):
            print(err_msg_unstaged)
            sys.exit(1)

        children_sequential = [
            c for c in children_filtered if c not in children_parallel
        ]

        for child in children_sequential:
            if not check_child_commit_exist_in_remote(parent, child):
                print(err_msg_unstaged)
                sys.exit(1)

    return all_children


def run():

    if len(sys.argv) < 2:
        return

    cmd = sys.argv[1]

    if cmd not in ['init', 'add', 'commit', 'push', 'init-gitsub']:
        sp.run(['git'] + sys.argv[1:])
        return

    parent_root_absolute = get_repo_root()

    if cmd == 'init-gitsub':
        f = f'{parent_root_absolute}/.gitsub'
        if os.path.exists(f):
            print('This repo already has a .gitsub file in its root.')
        else:
            print(f'New .gitsub file at: {f}')
            open(f, 'a').close()
        return

    if not is_repo_gitsub(parent_root_absolute):
        sp.run(['git'] + sys.argv[1:])
        return

    parent = get_parent_data(parent_root_absolute)

    children = get_children_from_fs(parent)

    if cmd == 'commit':
        children = validate_children(parent, children)

    if cmd == 'add':

        for child in children:
            rename_git_dir(
                repo_root=child.root_absolute,
                from_='.git',
                to='.gitsub_hidden',
            )

    # Run Git Command
    print(f"{fg.li_black}Gitsub: Run git command.{fg.rs}")
    sp.run(['git'] + sys.argv[1:])

    # Lock child repos
    for child in children:
        rename_git_dir(
            repo_root=child.root_absolute,
            from_='.gitsub_hidden',
            to='.git',
        )

    for child in children:
        update_gitsub_file(parent, child)
