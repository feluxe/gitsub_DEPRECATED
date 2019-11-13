from typing import List
from sys import stderr


def print(*args):
    s = ' '.join([str(arg) for arg in args]) + "\n"
    stderr.write(s)


def print_msg_unstaged():
    msg = (
        "Note: You cannot update a parent repo, as long as it contains subrepos with\n",
        "changes that haven't been pushed to their remote locations.\n"
    )
    stderr.write(" ".join(msg))


def print_cannot_find_child_repo_on_filesystem(repo_location: str):
    msg = (
        "Error: Cannot find locked child repo on file system.\n\n",
        "I cannot find a valid git repo at: " + repo_location + "\n",
        "You have two options:\n\n",
        "  A) Run 'git init-children' to ",
    )
    stderr.write(" ".join(msg))
