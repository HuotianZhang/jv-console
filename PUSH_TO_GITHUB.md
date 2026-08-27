# Pushing this to GitHub

The remote already exists and the first commit is on it:

```
origin  https://github.com/HuotianZhang/jv-console.git   (private)
```

So a push is just:

```powershell
cd D:\jv-console
git push origin main
```

Run it from a terminal on this machine. A shell reaching the folder over a
network mount cannot use the Windows credential store, so the push has to come
from here.

## If git complains about a lock file

A crashed run can leave `.git\*.lock` behind, and every later commit fails with
"Another git process seems to be running". Nothing is running — delete them:

```powershell
del .git\index.lock, .git\HEAD.lock, .git\refs\heads\main.lock -ErrorAction Ignore
git gc --prune=now
```

## Check before you push

`.gitignore` keeps measurement data and design material out: `*.dat`, `data/`,
`data.json`, `demo.html`, `design-system/`, `design-screens/`, `design-in/`,
`DESIGN_*.md`. `index.html` ships with an empty dataset — you load your own
scans through "Import files…" or by dropping `.dat` files on the left pane.

```powershell
git ls-files                                  # nothing but code and docs
Select-String -Path index.html -Pattern '"scans":\[\]' -SimpleMatch | Measure-Object
```

One match means the shipped page carries no data.
