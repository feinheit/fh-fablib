# fh-fablib: Replace Invoke with Typer

Branch: `mk/typer` (both fh-fablib and argocd repos)

## Goal

Replace Invoke's `@task` / `Collection` / CLI runner with Typer. Keep `fabric.Connection`
(and therefore paramiko) for SSH tasks — only the CLI plumbing changes.

**Problems with Invoke being solved:**
- Parser silently refuses to consume a second positional arg if it has a default value
  (`positional=["app", "cmd"]` with `cmd=""` doesn't work — Invoke only consumes
  positionals with *no* default)
- General parser fragility and slow maintenance

## What's done on `mk/typer`

### fh-fablib

`fh_fablib/__init__.py` rewritten:

- **Removed** the invoke monkey-patch block, `from fabric import Connection, task`,
  `from invoke import Collection`
- **Added** `import typer`, `import subprocess`, `import importlib.util`
- **`task`** — no-op decorator (`fn=None, **kwargs` → returns fn unchanged); kept for
  backward compatibility while fabfiles migrate
- **`_Result`** — lightweight result object (`returncode`, `exited`, `stdout`, `stderr`)
  replacing invoke's `Result`
- **`run_local(cmd, *, hide, warn, replace_env, env)`** — now uses `subprocess.run`
  directly; no `ctx` parameter; `hide=True` captures output, otherwise streams
- **`run(conn, ...)`** — unchanged; still calls `fabric.Connection.run()` for SSH
- **`Connection`** — now subclasses `_FabricConnection` (renamed import to avoid
  circular class definition)
- **`environment(name, cfg)`** — returns a `typer.Typer` sub-app with a callback
  that calls `config.update(**cfg)` before any subcommand; all tasks from the parent
  `Collection` are registered under it so `fl production deploy` works
- **`Collection`** — subclasses `typer.Typer`; accepts optional name string as first
  positional arg; separates tasks from environment sub-apps; supports `default` setter
  (registers a callback that invokes the named task when no subcommand given);
  `add_collection(sub)` passes sub-app's own name explicitly to avoid Typer warning
- **`main()`** — walks up from cwd to find `fabfile.py`; does `os.chdir` and
  `sys.path.insert(0, ...)` into fabfile's directory; loads it via `importlib`;
  calls `ns()`
- **All internal tasks** — `ctx` removed from signatures; `run_local(ctx, ...)` →
  `run_local(...)`; `_concurrently(ctx, jobs)` → `_concurrently(jobs)`; type
  annotations added so Typer treats un-defaulted params as positional args

`pyproject.toml`:
- Added `typer>=0.9` to dependencies
- Entry point changed from `fabric.main:program.run` to `fh_fablib:main`

### argocd

All tasks and helpers migrated to the new API:
- `ctx` removed from every function signature
- `fl.run_local(ctx, cmd)` → `fl.run_local(cmd)` everywhere
- `_secrets_dict(ctx, app)` → `_secrets_dict(app)` in utils.py and callers
- `_s3cfg(ctx, app)` → `_s3cfg(app)` in utils.py and callers
- All `@fl.task(...)` decorators removed
- Type annotations added to positional parameters
- `fl run APP CMD` works correctly as true positionals (the original bug that forced
  `--cmd` is gone)

## What still needs doing

### 1. Drop the `fabric` dependency (optional but desirable)

Currently fh-fablib still depends on `fabric>=3` (which brings in `invoke` and
`paramiko`). We use fabric only for `fabric.Connection`. Two options:

**Option A — thin paramiko wrapper (~100 lines):**
Implement `Connection` directly on top of `paramiko`:
- `run(cmd, ...)` via `exec_command`, stream/capture stdout/stderr
- `cd(path)` context manager (prepend `cd path && ` to subsequent run calls)
- `put(src, dst)` / `get(src, dst)` via `paramiko.SFTPClient`
- Agent forwarding via `paramiko.AgentRequestHandler`
- Gateway/jump-host support via `paramiko`'s `sock=` parameter and `ProxyJump`

The tricky bits: `cd()` needs to compose with nested `cd()` calls, and gateway
support requires opening a transport through the gateway's channel.

**Option B — separate `fh_fablib.nine` module:**
Move all nine.ch SSH tasks into `fh_fablib/nine.py` which imports `fabric`.
Projects that don't use nine.ch (like argocd) pay zero cost. The main `__init__.py`
exports `NINE` by importing from `.nine`, so existing fabfiles need no changes.
Requires `fabric` to be an optional/extra dependency.

Option B is lower risk; option A is the clean break.

### 2. Migrate remaining fabfiles

Every project with a `fabfile.py` that uses the old API needs:
- Remove `ctx` from task function signatures
- `fl.run_local(ctx, cmd)` → `fl.run_local(cmd)`
- Remove `@fl.task(positional=[...])` decorators (or leave as no-ops)
- Add type annotations to positional args so Typer parses them correctly
- `_secrets_dict(ctx, app)` → `_secrets_dict(app)` where applicable

The migration is mechanical. `_bool(include_www)` calls can be replaced with a
native `bool` parameter.

### 3. Known Typer behaviours to be aware of

- Boolean parameters with no default (required bools) are unusual; use `bool = False`
  with explicit `--flag/--no-flag` or `Annotated` for required booleans
- `also: list[str] = []` for iterable args works; `iterable=["also"]` from invoke
  is gone
- Command names: underscores become dashes automatically (`nine_vhost` → `nine-vhost`)
- Short flags are NOT auto-generated (Typer requires explicit `Option("-f", "--foo")`);
  this matches the old `auto_shortflags=False` default we used everywhere

### 4. `_find_base()` / module-level `os.chdir`

The old flow relied on fh_fablib being imported *from* fabfile.py (so the stack
contained a fabfile.py frame). In the new `main()` flow, fh_fablib is imported
earlier (by the `fl` script), so `_find_base()` returns `None` at module load time
and the `os.chdir` in module-level code is a no-op.

The `os.chdir` and `sys.path.insert` in `main()` compensate for this. The
`_find_base()` machinery and module-level `os.chdir(config.base)` are now dead code
for the normal `fl` flow — they only fire when a fabfile does `import fh_fablib`
outside of the `fl` runner (e.g. in tests). Consider cleaning this up.
