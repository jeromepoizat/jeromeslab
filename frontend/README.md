# Jerome's Laboratory frontend

The local browser client uses React, TypeScript, and Vite.

From this directory:

```shell
pnpm install --frozen-lockfile
pnpm dev
```

During development, Vite binds to `127.0.0.1` and proxies `/api` to the FastAPI
service at `http://127.0.0.1:8000`.

Checks:

```shell
pnpm lint
pnpm build
```
