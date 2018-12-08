
# Gitsub

## Description

A simple wrapper around git that allows for nested repositories.

It's much simpler than `submodule` and `subtree`. You don't need to remeber any complicated commands. This wrapper is just a couple hunderd lines of code, but very effective.

If you run `git add -A` in a parent-repo that contains one or several child-repos, the files of the child-repos will be added to the parent-repo, except for their `.git` directories.

Without `gitsub` git would complain if you run `git add -A` in a directory that itself contains a `.git` in one of its subdirecotries. `gitsub` works around this by temporarily renaming each `.git` to `.git_hidden` for the duration of the command.

In order to change child-repos, you just cd into them and run your git commands as usual. Every child-repo contains a file `.gitsub` that stores the current active branch-name, the last commit-hash and the remote location. This file is updated automatically every time you commit something to a child-repo. Child-repos may add `.gitsub` to `.gitignore`.

If you clone a parent-repo that contains child-repos from a remote location you have to run `gitsub init-children`. You have to do that since the parent-repo does not store the `.git` of its children itself, just the `.gitsub` files, from which it gets the information branch-name, commit-hash and remote location.

You cannot commit to a parent-repo, as long as any of its child-repos have changes, that were not yet pushed to remote. This ensures that the state of the parent-repo remains reproducible.


## Example

Let's say you clone a parent-repo, that contains two children from a remote location:

`git clone http.../parent_repo.git`

You get this:

```
 parent_repo
 ├── .git
 ├── .gitsub    # Stores information about child-repos
 ├── foo
 ├─ child_repo1
 │    ├── .gitsub    # Stores branch-name, commit-hash and remote location
 │    └── bar
 └── child_repo2
      ├── .gitsub    # Stores branch-name, commit-hash and remote location
      └── baz

```

In order to populate the children with their git repos, you run:

`git init-children`

Now you have the children with their git repos set to the branch and commit-hash stored in each `.gitsub`:

```
 parent_repo
 ├── .git
 ├── .gitsub
 ├── foo
 ├─ child_repo1
 │    ├── .git
 │    ├── .gitsub
 │    └── bar
 └── child_repo2
      ├── .git
      ├── .gitsub
      └── baz

```

Let's say you want to change file `baz` in `child_repo2` and commit:

```
$ cd child_repo2
$ echo "hello" > baz
$ git add -A
$ git commit -m 'Change file "baz"'
```

`child_repo2/.gitsub` now contains the hash of the latest commit.

If you now cd back to the parent-repo and run a `git commit` you would get an error from `gitsub` complaining that you haven't pushed the commit of `child_repo2` to its remote location yet.

In order to update the parent-repo we first need to run `git push` in `child_repo2`:

```
# we are still in parent_repo/child_repo2/
$ git push origin master
```

Now we can cd back to the parent and commit the changes that we have in `child_repo2` there as well:

```
cd .. # (we are now in parent_repo)
$ git add -A    
$ git commit -m "Change file 'baz' in child-repo."
$ git push origin master
```

This is pretty much it. The rest is just git as you know it. You just cd back and forth and run your git commands. The only limitation is that you have to push changes of child-repos to their remote location before you can commit to a parent.


## Install

You can build `gitsub` from source and put it into `PATH`:

```
cd /tmp

git clone https://github.com/feluxe/gitsub.git

cd gitsub

pipenv install --dev --pre

pipenv run python make.py build

sudo cp dist/pyinstaller/gitsub /usr/local/bin
```

## Development

Build from source and run test command. This leaves you with a `pysub` binary and a test boilerplate in `/tmp/gitsub` to play with.

```
git clone https://github.com/feluxe/gitsub.git

cd gitsub

pipenv install --dev --pre

pipenv run python make.py build

pipenv run python make.py test
```
