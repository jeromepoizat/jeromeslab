# ADR 0007: Self-bootstrapping installation

- Status: Accepted
- Date: 2026-09-07

## Context

Jerome's Laboratory should be easy to pull and run. Requiring an ordinary user to
understand or separately install Python, Node.js, `uv`, pnpm, or virtual
environments would undermine the local-application experience.

## Decision

Ordinary users will not be required to preinstall language runtimes or package
managers.

For source checkouts, provide idempotent PowerShell and POSIX-shell bootstrap
scripts. They download pinned tools into ignored project-local storage, install a
managed Python through `uv`, synchronize Python and frontend dependencies from
committed lockfiles, build the frontend, and leave simple start wrappers. They do
not require administrator access, modify global PATH, or install secrets.

Downloads use pinned versions and verify publisher-provided checksums where
available. Existing compatible local bootstrap assets may be reused, but system
tool detection is an optimization rather than a prerequisite.

For published releases, prefer OS-specific self-contained packages containing the
built frontend, Python runtime, backend, and dependencies. Release builds run on
their target OS; they are not cross-compiled. A native package is the preferred
end-user experience once packaging is established.

## Consequences

A source user still needs Git to pull the repository, an OS-provided script host,
network access on first install, and enough disk space. The bootstrap becomes
security-sensitive code and needs checksum validation, proxy/error handling,
idempotency tests, and a documented supported OS/CPU matrix.

Development retains Node.js because the frontend must be built, but native release
users will not receive or operate the frontend toolchain. CI and releases become
more complex because each supported OS needs independent bootstrap and packaging
coverage.
