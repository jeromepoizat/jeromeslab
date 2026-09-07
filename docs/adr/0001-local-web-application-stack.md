# ADR 0001: Local web application stack

- Status: Accepted
- Date: 2026-09-07

## Context

The UI needs durable project navigation, expandable workflow history, long-page
navigation, settings, live job progress, and project forks. The normal product is
a local, single-user application.

## Decision

Use React, TypeScript, and Vite for the browser client. Use Python, FastAPI,
Uvicorn, and Pydantic for the local service. The launcher binds to `127.0.0.1` by
default and opens the user's browser. Start with HTTP polling for live updates.

Do not use Streamlit or Next.js unless a later ADR demonstrates a requirement.
Docker is optional, not the normal launch path.

## Consequences

Frontend and backend have a versioned HTTP boundary and can be tested separately.
The product gains interaction flexibility at the cost of two build toolchains.
Localhost security and cross-platform launch behavior require deliberate tests.

