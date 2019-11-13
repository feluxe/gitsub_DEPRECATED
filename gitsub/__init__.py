import os
import shutil
import sys
import toml
import subprocess as sp
from typing import List, Optional, Union, Tuple, Generator
from glob import iglob
from dataclasses import dataclass, asdict

from .lib import Child, Remote
from . import err


def get_repo_root() -> str:

    cmd = ['git', 'rev-parse', '--show-toplevel']

    r = sp.run(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

    if r.returncode == 128:
        pass
    elif r.returncode == 0:
        pass
    else:
        sys.stderr.write(r.stderr)
        sys.exit(1)

    repo_root = r.stdout.decode('utf8').replace('\n', '')

    if not repo_root:
        sys.stderr.write("Error: Cannot find git repo root. ")
        sys.stderr.write("Are you sure you are in a git repo?\n")
        sys.exit(1)

    return repo_root


def is_repo_gitsub(repo_root: str) -> bool:

    if not repo_root:
        return False

    if os.path.isfile(f'{repo_root}/.gitsub'):
        return True
    else:
        return False


def validate_git_configuration():
    """
    Check if '.gitsub_hidden' is ignored globally.
    """
    r = sp.run(
        ['git', 'config', '--get', 'core.excludesfile'],
        stdout=sp.PIPE,
    )

    out = r.stdout.decode('utf8')
    ignore_files = ['.gitignore']

    for line in out.splitlines():
        ignore_files.append(os.path.expanduser(line))

    for path in ignore_files:
        if os.path.isfile(path):
            with open(path, 'r') as f:
                for line in f.readlines():
                    if line.strip() in ['.gitsub_hidden/', '**/.gitsub_hidden']:
                        return

    sys.stderr.write(
        "Error: Cannot find '.gitsub_hidden/' entry in global or local "\
        "'.gitignore' file."\
        "\n\nAdd this line:\n\n    .gitsub_hidden/\n\nto your global or "\
        "local gitignore file.\n"
    )
    sys.exit(1)


def run_git_cmd(cmd, args, with_msg=True):
    if with_msg:
        print(f"{fg.li_black}Gitsub: Run git command.{fg.rs}")
    sp.run(['git'] + [cmd] + args)


def run():
    """
    Run Main Execution
    """
    if len(sys.argv) < 2:
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Skip gitsub execution for git commands, which are not related to gitsub.

    gitsub_related_commands = [
        'add',
        'commit',
        'push',
        'init-parent',
        'init-child',
        'check-children',
    ]

    if cmd not in gitsub_related_commands:
        run_git_cmd(cmd, args, with_msg=False)
        return

    parent_root = get_repo_root()

    if cmd != 'init-parent' and not is_repo_gitsub(parent_root):
        run_git_cmd(cmd, args, with_msg=False)
        return

    # Run gitsub related commands.

    if cmd != 'init-parent':
        validate_git_configuration()

    if cmd == 'init-parent':
        from . import init_parent
        init_parent.run(parent_root)

    elif cmd == 'init-child':
        from . import init_child
        init_child.run(parent_root, args)

    # elif cmd == 'check-children':
    #     parent = load_parent_data(parent_root)
    #     fs_children = load_children_from_fs(parent, search=True)
    #     validate_children(parent, fs_children)

    elif cmd == 'add':
        from . import add_
        add_.run(parent_root, args)

    # elif cmd == 'commit':
    #     fs_children = load_children_from_fs(parent)
    #     validate_children(parent, fs_children)
    #     run_git_cmd(cmd, args)

    # # WHEN DO WE LOCK??????????????
    # lock_children(parent, children)

    # if cmd in ['check-children']:
    #     return

    # # Run Git Command
    # run_git_cmd(cmd, args)

    # # Cleanup
    # for child in children:
    #     rename_git_dir(child.root_absolute, '.gitsub_hidden', '.git')
