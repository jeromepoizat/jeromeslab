# Contributing to Jerome's Laboratory

Thank you for helping build Jerome's Laboratory. The project is still early, so
read [the current status](docs/STATUS.md) and the relevant architecture or
workflow documentation before starting a change. Open an issue before a large
change when its product behavior or scientific method has not been decided.

## Install from a source checkout

Ordinary contributors do not need Python, Node.js, `uv`, or pnpm preinstalled.
The bootstrap keeps its downloaded runtimes and caches inside the ignored
`.runtime/` directory and creates the ignored Python `.venv`.

On Windows, run:

```powershell
.\install.ps1
```

Double-clicking `install.bat` performs the same installation.

On macOS or glibc-based Linux, run:

```sh
chmod +x install.sh start.sh
./install.sh
```

The installer verifies pinned runtime downloads, installs both committed
lockfiles, and builds the frontend. It is safe to rerun after pulling changes.

## Start the application

On Windows, run `start.bat` or:

```powershell
.\start.ps1
```

On macOS or Linux, run:

```sh
./start.sh
```

The launcher binds only to `127.0.0.1`, chooses an available port, opens the
default browser after the health check succeeds, and keeps server logs visible.

## Run the verified checks

The following commands use only the project-local toolchain installed by the
bootstrap.

### Windows

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tests
.\.venv\Scripts\pytest.exe

Push-Location frontend
& ..\.runtime\node\node.exe ..\.runtime\pnpm\node_modules\pnpm\bin\pnpm.cjs lint
& ..\.runtime\node\node.exe ..\.runtime\pnpm\node_modules\pnpm\bin\pnpm.cjs build
Pop-Location
```

### macOS or Linux

From the repository root:

```sh
./.venv/bin/ruff check .
./.venv/bin/mypy src tests
./.venv/bin/pytest

(
  cd frontend
  ../.runtime/node/bin/node ../.runtime/pnpm/lib/node_modules/pnpm/bin/pnpm.cjs lint
  ../.runtime/node/bin/node ../.runtime/pnpm/lib/node_modules/pnpm/bin/pnpm.cjs build
)
```

Developers who intentionally prefer global tools can use the optional manual
setup in the [README](README.md#manual-developer-setup-optional).

## Pull requests and continuous integration

Keep a pull request focused and update tests and documentation with behavior
changes. Do not commit `.runtime/`, `.venv/`, `node_modules/`, built frontend
output, application data, credentials, or API keys.

GitHub Actions runs the bootstrap twice and then runs the checks on six hosted
runner combinations:

- Windows x64 and ARM64
- Linux x64 and ARM64
- macOS ARM64 and Intel

All six jobs must pass. Because the workflow disables fail-fast behavior, inspect
every job even when one platform fails. On the GitHub repository, open
**Actions**, select **Cross-platform CI**, choose a run, and then select a job.
Expand the first failed step to inspect its output; **Set up job** identifies the
exact runner image.

## Project invariants

- Preserve exact inputs, original outputs, human-edited effective versions, and
  provenance links.
- Keep scientific workflow logic independent of specific LLM and literature
  providers.
- Never store API secrets in the repository, browser storage, SQLite, logs,
  artifacts, exceptions, or provenance.
- Keep the default server binding on `127.0.0.1`.
- Keep installation usable without administrator rights, global PATH changes, or
  preinstalled language runtimes.
- Treat later scientific stages as design work until the repository documentation
  explicitly accepts their behavior.

Architectural decisions are indexed in [docs/DECISIONS.md](docs/DECISIONS.md).
Add an ADR only when a decision constrains architecture, security, scientific
validity, data compatibility, or user-visible workflow semantics.
