# Pushing this to GitHub

The repository is already initialised and committed — history and all. You only
need to create the remote and push.

## With the GitHub CLI

```bash
gh repo create jv-console --private --source=. --remote=origin --push
```

## Without it

Create an empty **private** repository named `jv-console` at
<https://github.com/new> — no README, no .gitignore, no licence, so the first
push is not rejected. Then:

```bash
git remote add origin https://github.com/HuotianZhang/jv-console.git
git push -u origin main
```

## Check before you push

`.gitignore` excludes `*.dat`, `data/`, `data.json` and `demo.html`, so
measurement data cannot be committed by accident. `index.html` ships with an
empty dataset. Confirm with:

```bash
git ls-files | xargs ls -la
grep -c '"scans":\[\]' index.html   # 1 = empty dataset, as intended
```
