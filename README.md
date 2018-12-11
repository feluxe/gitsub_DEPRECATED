
# Gitsub

## Description

A simple but effective wrapper around git that allows for (deeply) nested repositories.

It's much simpler than `submodule` and `subtree`. There are no complicated commands to remember... Just cd into your repo (parent or child doesn't matter) and run your git commands as usual.


## How it works

If you run `git commit ...` in a parent-repo that contains one or several child-repos, the files of the child-repos will be added to the parent-repo, except for their `.git` directories.

Without `gitsub` git would complain if you run `git add -A` in a directory that itself contains a `.git` dir in one of its subdirecotries. `gitsub` works around this by temporarily renaming each `.git` to `.gitsub_hidden` for the duration of the command.

If you run `git commit ...` on a parent-repo, the current *branch-name*, *commit-hash* and *remote-url* of each child-repo is locked into `.gitsub` (a file that sits in the root directory of the parent).

Since the parent-repo does't contain the `.git` direcories of its children, you have to run `git init-children` after you clone a parent-repo. That will automatically clone each child-repo into the correct sub direcotry of its parent and set the HEAD of each child-repo to the branch/commit that was locked in `.gitsub`.

If you try to commit to a parent-repo while one of its children contains uncommited changes, gitsub will complain and tell you to commit and push the changes in order to proceed. This mechanism is needed for the parent to keep its child-repo files in sync with their commits, so that a `git clone myparent` and a `git inint-children` always create the same tree.

I think that's pretty much all you need to know. It's simple but it works intuitivly well. Gitsub will warn you whenever something is needed.



## Example (Walkthrough)

Let's start from scratch.

We have a normal git repo called `parent_repo`. The repo already contains two directories named `child_repo1` and `child_repo2`, but they don't contain anything yet.

```
 parent_repo
 ├── .git
 ├── foo
 ├── child_repo1
 └── child_repo2

```

Now let's init git repos for our children and create a text file for each:

```
$ cd child_repo1
$ git init
$ touch bar
$ cd ..
$ cd child_repo2
$ git init
$ touch baz
```

This leaves us with this:

```
 parent_repo
 ├── .git
 ├── foo
 ├── child_repo1
 │   ├── .git   # New
 │   └── bar    # New
 └── child_repo2
     ├── .git   # New
     └── baz    # New

```

Now we make our parent repo a *gitsub parent* by running `git init-parent` in `parent_repo`. This will create a `.gitsub` file for locking child data.

We have this now:


```
 parent_repo
 ├── .git
 ├── .gitsub    # New
 ├── foo
 ├─ child_repo1
 │   ├── .git
 │   └── bar
 └── child_repo2
      ├── .git
      └── baz

```

Now I want to `add / commit / push` the changes for the parent repo, but if I run:

```
cd /parent_repo
git add -A
git commit -m 'changes'
```

I get an error such as this one:

> Current commit cannot be found on remote for: child_repo1

That means we have to run `commit/push` for child_repo1 and 2 in order to commit to our parent. For each child we run:

```
cd /parent_repo/child_repo[1|2]
$ git add -A
$ git commit -m 'changes'
$ git push origin master
```

Now I can cd back to the parent and push the changes without gitsub complaining.

Ok then... 

Now let's imagine we go to another computer and continue working from there.

We clone the parent repo: `git clone http://...parent_repo.git`

And get this:

```
 parent_repo
 ├── .git
 ├── .gitsub
 ├── foo
 ├── child_repo1
 │    └── bar
 └── child_repo2
      └── baz

```
As you see, the children don't contain a `.git` dir. That's because the parent never stores the .git directories of its children. Instead, it stores the remote-urls, current commit-hash and branch-name for each child in `.gitsub`.

In order to populate the children with their git repos, you run:

`git init-children`

This will give you the properly nested repo tree:

```
 parent_repo
 ├── .git
 ├── .gitsub
 ├── foo
 ├─ child_repo1
 │    ├── .git   # This was added
 │    └── bar
 └── child_repo2
      ├── .git  # This was added
      └── baz

```

This is pretty much it. The rest is just git as you know it. You cd back and forth from repo to repo and run your git commands. The only limitation is that you have to push changes of child-repos to their remote location before you can commit to a parent. But gitsub will warn you when this is the case.



## Commands

`git init-parent`

Run this command in a git repo to create a `.gitsub` file in its root.


`git init-children`

After you clone a parent-repo, you need to run this command in oder to populate the children with their `.git` direcotry and set each HEAD to the correct branch/commit.


`git check-children`

Run this command to check if all children are ready to be commited. You usually don't have to do this, since gitsub will warn you anyways. But it might be handy in some situations.


## Requirements

* Unix like system
* Tested with `git version 2.19`
* Each child-repo must have a remote location set.
* A cache directory: `~/.cache`



## Install

**build from source**

You can build `gitsub` from source and put it into `PATH`:

```
cd /tmp

git clone https://github.com/feluxe/gitsub.git

cd gitsub

pipenv install --dev --pre

pipenv run python make.py build

sudo cp dist/pyinstaller/gitsub /usr/local/bin
```

**add alias**

You can call the `gitsub` directly or add an alias to your terminal `rc` file, e.g.

`~/.zshrc`

    alias git=gitsub


## Development

Build from source and run test command. This leaves you with a `pysub` binary and a test boilerplate in `/tmp/gitsub` to play with.

```
git clone https://github.com/feluxe/gitsub.git

cd gitsub

pipenv install --dev --pre

pipenv run python make.py build

pipenv run python make.py test
```
