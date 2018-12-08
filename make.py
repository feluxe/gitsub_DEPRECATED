import subprocess as sp
import os
import sys
import shutil
from cmdi import print_summary, command
from buildlib import buildmisc, git, project, yaml
from docopt import docopt

interface = """
    Install:
        pipenv install --dev --pre
        pipenv run python make.py

    Usage:
        make.py build <tool> [options]
        make.py deploy [options]
        make.py test [options]
        make.py bump [options]
        make.py git [options]
        make.py -h | --help

    Commands:
        build <tool>        Build binary ('dist/gitsub') from source. <tool> can
                            be 'pyinstaller' or 'nuitka'.

    Options:
    -l, --libpy <path>       Location of libpython. E.g. /usr/local/lib/
    -h, --help               Show this screen.
"""

proj = yaml.loadfile('Project')


class Cfg:
    version = proj['version']
    registry = 'mw-pypi'
    libpy_path = '/usr/local/lib'


@command
def build(uinput: dict, cfg: Cfg):

    tool = uinput['<tool>'] or 'pyinstaller'

    if tool == 'pyinstaller':

        env = os.environ.copy()

        # Python Libray location differs from os to os.
        lib_path = uinput['--libpy'] or env.get('LD_LIBRARY_PATH') or \
                    cfg.libpy_path

        # pyinstaller requires us to set the python library path via envvar.
        if 'LD_LIBRARY_PATH' not in env:
            env['LD_LIBRARY_PATH'] = lib_path

        cmd = 'pyinstaller\
        -y --onefile\
         --workpath build/pyinstaller\
         --specpath build/pyinstaller\
         --distpath dist/pyinstaller\
         --name gitsub\
         entry.py'

        try:
            sp.run(cmd, env=env, shell=True, check=True)
        except sp.SubprocessError as e:
            print(e)
            print(
            "\nYou may need to use the --libpy option to specify a lib dir.\n"\
            "Search for libpython: 'find / -type f -name libpython*' "
            )
            sys.exit(1)

        print(
            '\nFor installation run:\n\nsudo cp dist/pyinstaller/gitsub /usr/local/bin\n'
        )

    elif tool == 'nuitka':

        print(
            'WARNING: As long as the --standalone option does not work, the'\
            'resulting binary relies on the Python environment of the target'\
            'system. You should compile with PyInstaller instead.\n'
        )

        cmd = 'python -m nuitka\
        --follow-imports\
        --lto\
        --output-dir dist/nuitka\
        entry.py'

        sp.run(cmd, shell=True)

        print(
            '\nFor installation run:\n\nsudo cp dist/nuitka/entry.bin /usr/local/bin/gitsub\n'
        )

    return


def deploy(cfg: Cfg):
    print('Deploy command not implemented.')


def test(cfg: Cfg):

    shutil.rmtree('/tmp/gitsub/', ignore_errors=True)
    os.makedirs('/tmp/gitsub/')
    shutil.copytree(src='tests', dst='/tmp/gitsub/tests')
    print('Created test boilerplate directory at: /tmp/gitsub/tests')


def bump(uinput, cfg: Cfg):

    results = []

    if project.prompt.should_bump_version():

        r1 = project.cmd.bump_version()

        cfg.version = r1.val

        r2 = buildmisc.cmd.bump_py_module_version(
            file='gitsub/__init__.py',
            new_version=cfg.version,
        )

        results.extend([r1, r2])

    new_release = cfg.version != proj['version']

    results.extend(git.seq.bump_git(cfg.version, new_release))

    build(uinput, cfg)

    return results


def run():

    cfg = Cfg()
    uinput = docopt(interface)
    results = []

    if uinput['build']:
        results.append(build(uinput, cfg))

    if uinput['deploy']:
        results.append(deploy(cfg))

    if uinput['test']:
        results.append(test(cfg))

    if uinput['git']:
        results.append(git.seq.bump_git(cfg.version, new_release=False))

    if uinput['bump']:
        results.extend(bump(uinput, cfg))

    print_summary(results)


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n\nScript aborted by user.')
