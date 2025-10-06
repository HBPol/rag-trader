# RAGTrader Web

Next.js + TypeScript frontend for RAGTrader. The current scaffold provides
our layout shell, styling entry point, mocked auth wiring, and a simple
component test so we can iterate with TDD in upcoming issues.

## Development

```bash
pnpm install # or npm install / yarn install
pnpm test
```

## Authentication gate workflow

Authentication is not wired to a real identity provider yet. Instead, the
app bootstraps an `AuthProvider` (in `src/app/layout.tsx`) that reads the
`NEXT_PUBLIC_AUTH_MOCK_STATE` environment variable. Two values are
understood:

- `authenticated` – renders the main application shell.
- Any other value – displays the locked-state messaging.

During development you can flip the experience without restarting the dev
server:

```bash
NEXT_PUBLIC_AUTH_MOCK_STATE=authenticated pnpm dev
```

Unit tests can also import the `AuthProvider` and pass their own
`isAuthenticated` value when rendering components, which mirrors the React
Testing Library coverage that asserts both locked and unlocked states.
