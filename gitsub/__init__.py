import subprocess as sp
import os
import sys
import toml
from glob import glob
from dataclasses import dataclass
from slib.term.style import fg

CACHEDIR = '/home/felix/.cache/gitsub'

err_msg_unstaged = """
Note: You cannot update a parent repo, as long as it contains subrepos with changes 
that haven't been pushed to their remote locations.
"""


def get_repo_root():

    cmd = ['git', 'rev-parse', '--show-toplevel']

    r = sp.run(cmd, stdout=sp.PIPE, stderr=sp.PIPE)

    if r.returncode == 128:
        print("No git repo.")
    elif r.returncode == 0:
        pass
    else:
        print(r.stderr)
        sys.exit(1)

    repo_root = r.stdout.decode('utf8').replace('\n', '')

    return repo_root


def is_repo_gitsub(repo_root):

    if not repo_root:
        return False

    if os.path.isfile(f'{repo_root}/.gitsub'):
        return True
    else:
        return False


@dataclass
class Repo:
    name: str
    git_user: str
    branch: str
    commit: str
    remote: str
    is_ssh: str
    ssh_remote: str
    location: str
    cache_location: str


def gather_subrepo_data(repo_root, repo_data):

    subrepos = []

    for subrepo_path in repo_data['subrepos']['locations']:

        subrepo_root = f'{repo_root}/{subrepo_path}'
        subrepo_gitsub_file = f'{subrepo_root}/.gitsub'

        with open(subrepo_gitsub_file, 'r') as f:
            subrepo_data = toml.loads(f.read())

        remote_split = subrepo_data['repoinfo']['remote'].split('/')
        name = remote_split[-1]
        git_user = remote_split[-2]

        repo = Repo(
            branch=subrepo_data['repoinfo']['branch'],
            commit=subrepo_data['repoinfo']['commit'],
            remote=subrepo_data['repoinfo']['remote'],
            is_ssh=subrepo_data['repoinfo'].get('ssh'),
            ssh_remote=f"git@github.com:{git_user}/{name}",
            name=name,
            git_user=git_user,
            location=subrepo_path,
            cache_location=f'{CACHEDIR}/{git_user}/{name}',
        )

        subrepos.append(repo)

    return subrepos


def check_subrepos_for_unpushed_changes(repo_root, subrepos):

    print(
        f"{fg.li_black}Gitsub: Checking subrepos for unstaged changes.{fg.rs}"
    )

    for repo in subrepos:

        subrepo_root = f'{repo_root}/{repo.location}'

        cmd = ['git', 'status', '-s']
        r = sp.run(cmd, cwd=subrepo_root, stdout=sp.PIPE)
        changes = r.stdout.decode('utf8').replace('\n', '')

        if changes != '':
            print(f"\n    Unstaged Changes in: {repo.location}")
            print(err_msg_unstaged)
            sys.exit(1)


def commit_exists(repo_root, commit):

    cmd = ['git', 'cat-file', '-t', commit]
    r = sp.run(cmd, cwd=repo_root, stdout=sp.PIPE, stderr=sp.PIPE)
    out = r.stdout.decode('utf8').replace('\n', '')

    if out == 'commit':
        return True
    else:
        return False


def filter_subrepo_not_changed_locally(repo_root, subrepos):

    changed = []

    for subrepo in subrepos:
        cmd = ['git', 'status', '-s', subrepo.location]
        r = sp.run(cmd, cwd=repo_root, stdout=sp.PIPE)
        out = r.stdout.decode('utf8').replace('\n', '')

        if out:
            changed.append(subrepo)

    return changed


def check_subrepos_commit_exist_in_remote(repo_root, subrepos):

    procs = []

    for repo in subrepos:

        if not os.path.exists(f'{repo.cache_location}/.git'):

            print(
                f"{fg.li_black}Gitsub: Cloning repo into cache-dir for:{fg.rs} {repo.location}"
            )

            cmd = ['git', 'clone', repo.remote, repo.cache_location]
            procs.append(sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE))

    for p in procs:
        p.communicate()

    procs = []

    for repo in subrepos:

        print(
            f"{fg.li_black}Gitsub: Updating (fetch) cached repo for: {repo.location}{fg.rs}"
        )

        if repo.is_ssh == True:
            cmd = ['git', 'remote', 'set-url', 'origin', repo.ssh_remote]
            sp.run(cmd, stdout=sp.PIPE, cwd=repo.cache_location)

        cmd = ['git', 'fetch', 'origin', repo.branch]
        procs.append(
            sp.Popen(
                cmd, cwd=repo.cache_location, stdout=sp.PIPE, stderr=sp.PIPE
            )
        )

    for p in procs:
        p.communicate()

    for repo in subrepos:

        if not commit_exists(repo.cache_location, repo.commit):
            print(repo)
            print(
                f"\n    Current commit cannot be found on remote for: {repo.location}"
            )
            print(err_msg_unstaged)
            sys.exit(1)


def get_current_branch(repo_root):
    cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
    r = sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)
    branch = r.stdout.decode('utf8').replace('\n', '')

    return branch


def get_current_commit(repo_root):
    cmd = ['git', 'rev-parse', '--verify', 'HEAD']
    r = sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)
    commit = r.stdout.decode('utf8').replace('\n', '')

    return commit


def update_gitsub_file(repo_root):

    gitsub_file = f'{repo_root}/.gitsub'

    with open(gitsub_file, 'r') as f:
        gitsub_data = toml.loads(f.read())

    if not gitsub_data.get('repoinfo'):
        return

    branch = get_current_branch(repo_root)
    commit = get_current_commit(repo_root)

    gitsub_data['repoinfo']['branch'] = branch
    gitsub_data['repoinfo']['commit'] = commit

    with open(gitsub_file, 'w') as f:
        print(f"{fg.li_black}Gitsub: Updating .gitsub file{fg.rs}")
        f.write(toml.dumps(gitsub_data))


def rename_git_dirs(subrepos, from_='', to=''):

    print(f"{fg.li_black}Gitsub: Renaming {from_} -> {to}{fg.rs}")

    for repo in subrepos:

        src = f'{repo.location}/{from_}'
        dst = f'{repo.location}/{to}'

        if os.path.exists(src):
            os.rename(src, dst)


def force_add_gitsub_files(repo_root, subrepos):

    for repo in subrepos:
        cmd = ['git', 'add', '--force', f'{repo.location}/.gitsub']
        sp.run(cmd, stdout=sp.PIPE, cwd=repo_root)


def run():

    repo_root = get_repo_root()
    repo_gitsub_file = f'{repo_root}/.gitsub'

    if len(sys.argv) < 2:
        return

    cmd = sys.argv[1]

    # if cmd not in ['add', 'commit', 'push']:
    #     return

    if not is_repo_gitsub(repo_root):
        sp.run(['git'] + sys.argv[1:])
        return

    with open(repo_gitsub_file, 'r') as f:
        repo_data = toml.loads(f.read())

    if repo_data.get('repoinfo'):
        update_gitsub_file(repo_root)

    if repo_data.get('subrepos'):

        subrepos = gather_subrepo_data(repo_root, repo_data)

        filtered = filter_subrepo_not_changed_locally(repo_root, subrepos)

        if filtered:
            check_subrepos_for_unpushed_changes(repo_root, filtered)
            check_subrepos_commit_exist_in_remote(repo_root, filtered)

        if cmd == 'add':

            force_add_gitsub_files(repo_root, subrepos)

            rename_git_dirs(
                subrepos,
                from_='.git',
                to='.git_hidden',
            )

    # RUN GIT COMMAND
    print(f"{fg.li_black}Gitsub: Running git command.{fg.rs}")
    sp.run(['git'] + sys.argv[1:])

    if repo_data.get('subrepos'):
        rename_git_dirs(
            subrepos,
            from_='.git_hidden',
            to='.git',
        )

    if repo_data.get('repoinfo'):
        update_gitsub_file(repo_root)
