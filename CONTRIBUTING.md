# Adding a package

1. **Make it.** In Lasso, turn on Settings › Packages › Developer mode and choose **New Package…**, or
   use `lasso-pkg new <search|send|prompt|shortcut|script> <folder>`. The format and every rule are in
   [PACKAGES.md](https://github.com/civarry/lasso-app/blob/main/docs/PACKAGES.md); a gentler guide is
   [CONTRIBUTING-PACKAGES.md](https://github.com/civarry/lasso-app/blob/main/docs/CONTRIBUTING-PACKAGES.md).
2. **Try it.** In Developer mode, **Load Folder…** runs it straight from your folder and reloads when you
   save. Or: `lasso-pkg run <folder> <command> --text "…"`.
3. **Check it.** `lasso-pkg validate <folder> --catalog` runs what CI runs.
4. **Submit it.** Put the folder at `packages/<id>/` and open a pull request.

## What a maintainer looks for

- **The README** says, plainly: what it does, what it sends where, what it needs (a key and where to get
  one, a tool to install, a Shortcut to make), and what a free tier allows.
- **Least power.** Only the hosts it needs. A script asks for `network` only if it must. No `requires`
  it doesn't use.
- **Scripts** are short and readable: each one is read line by line. No downloading and running code,
  no reading outside its own folders, nothing obfuscated or minified.
- **Limits** sit under a service's free tier; a small tier uses `"role": "reserve"`.
- **An update** raises `version`. An update that changes a script, adds a host or asks for more is
  reviewed again in Lasso by everyone who installed it.

## Building lasso-pkg

It's built from Lasso's own package engine:

```
git clone https://github.com/civarry/lasso-app
lasso-app/Tools/lasso-pkg/build.sh ~/bin/lasso-pkg
```

Needs the Xcode command-line tools.
