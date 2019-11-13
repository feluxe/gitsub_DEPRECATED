import os
import shutil
import sys
import subprocess as sp
import pathlib

from .lib import load_locked_children, TEMPDIR
from . import err


def init_child(locked_child):

    git_dir = f"{locked_child.root_relative}/.git"

    if not os.path.isdir(git_dir):

        clone_ok = False

        if not os.path.exists(locked_child.root_absolute):
            os.makedirs(locked_child.root_absolute)

        for remote in locked_child.remotes:

            tmp_dir = f"{TEMPDIR}{locked_child.root_absolute}"

            shutil.rmtree(tmp_dir, ignore_errors=True)

            r = sp.run(['git', 'clone', remote.url, tmp_dir], cwd='/tmp')

            if r.returncode == 0:
                clone_ok = True

                for fileref in pathlib.Path(tmp_dir).glob('**/*'):
                    src = str(fileref)
                    dst = src.replace(TEMPDIR, '')

                    if not os.path.exists(dst):
                        os.rename(src, dst)
                    else:
                        print("Exists:", dst)

            else:
                print("Cloning failed for:", remote.url)

            shutil.rmtree(tmp_dir, ignore_errors=True)

        if not clone_ok:
            err.print("Error: Cannot clone repo.")
            sys.exit(1)


def run(parent_root: str, args):
    """
    Parent repos do not contain '.git' directories of their children.
    This command allows you to download all .git dirs for each child into its
    sub-directory.

    This command should always be run after a parent was cloned.
    """
    # TODO: Make sure no .gitsub_hidden dir exists before this runs.

    init_all = '--all' in args

    locked_children = load_locked_children(parent_root)

    if init_all:
        for locked_child in locked_children:
            init_child(locked_child)
    else:
        selection = args[0].strip()
        for locked_child in locked_children:
            if selection == locked_child.root_relative:
                init_child(locked_child)
