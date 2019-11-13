import os

from . import lib, err


def sync_children(parent_root, locked_children):

    # Check if all locked items are found on fs

    for locked_child in locked_children:
        git_dir = f"{locked_child.root_absolute}/.git"
        git_dir_hidden = f"{locked_child.root_absolute}/.gitsub_hidden"

        if not any([os.path.exists(git_dir), os.path.exists(git_dir_hidden)]):
            print(
                "Warning .gitsub out of sync.\n\n"
                "There is a lock entry for a child-repo in .gitsub, but the git repo",
                "cannot be found on the file-system at: " + git_dir + "\n\n",
                "You have three options:\n\n",
                "1) Clone "
                "1) Download the missing child repo from its remote location. This will:\n",
                "   * Clone the missing child-repo from its remote into a temp-dir.\n",
                "   * Set HEAD to the commit that is locked in .gitsub.\n",
                "   * Move non-existing files/dirs from the cloned repo into the child-repo directory.\n\n",
                "2) Remove the missing child from the .gitsub file.\n\n",
                "3) Adjust .\n\n",
                "Please enter a number:",
            )

    fs_children = lib.search_children_on_fs(parent_root)


def run(parent_root: str, args):

    locked_children = lib.load_locked_children(parent_root)

    sync_children(parent_root, locked_children)

    # # Check if all fs_children are locked

    # for fs_child in fs_children:
    #     lib.rename_git_dir(fs_child.root_absolute, '.git', '.gitsub_hidden')

    # lib.run_git_cmd('add', args)

    # for child_fs in fs_children:
    #     lib.rename_git_dir(child_fs.root_absolute, '.gitsub_hidden', '.git')
