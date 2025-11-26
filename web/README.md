# RAGTrader Web

Next.js + TypeScript frontend for RAGTrader. The current scaffold provides
our layout shell, styling entry point, mocked auth wiring, and a component
library powered by [shadcn/ui](https://ui.shadcn.com) so we can iterate with
TDD in upcoming issues.

## Development

```bash
pnpm install # or npm install / yarn install
pnpm test -- --coverage
```

Install dependencies (`pnpm install`) before running the Vitest coverage gate so the command matches
the CI job that uploads `coverage/lcov.info` to Codecov.

### Lighthouse CI workflow

- Build the production bundle before auditing:

  ```bash
  pnpm build
  ```

- Run Lighthouse CI with the shared config to collect fresh reports and enforce the desktop
  performance (≥0.85) and accessibility (≥0.90) thresholds:

  ```bash
  pnpm lhci
  ```

  The `lhci` script starts the production server on port 3000 using `lighthouse.config.cjs`,
  runs the autorun flow, and writes HTML/JSON reports to `.lighthouseci/` for inspection.
  A non-zero exit code indicates the audited scores fell below the configured assertions.
  The config fixes the form factor to **desktop**, uses **3 runs** per URL to smooth variance,
  and applies Lighthouse throttling (`throttlingMethod: "simulate"`) with a ~40ms RTT,
  10Mbps throughput, and `cpuSlowdownMultiplier: 2` to mirror CI.

#### How to run locally

Use the same CI flow locally to reproduce scores and view the `.lighthouseci` artifacts:

```bash
pnpm build && pnpm lhci
open .lighthouseci/*.html # or explore the JSON reports in .lighthouseci/
```

## UI toolkit and styling conventions

- We use Tailwind CSS + shadcn/ui primitives that live under
  `src/components/ui`. The `@/lib/utils` module exposes a `cn` helper for
  composing Tailwind classes.
- The shadcn generator is configured through `components.json`. Use your
  package manager of choice to add new primitives, for example:

  ```bash
  pnpm dlx shadcn-ui@latest add button
  pnpm dlx shadcn-ui@latest add card
  pnpm dlx shadcn-ui@latest add input
  ```

  The tooling writes to the `@/components` alias and relies on
  `tailwind.config.ts` + `src/app/globals.css` for theme tokens.
- Shared surface-level styles should be expressed via Tailwind utility
  classes rather than bespoke CSS modules. Reach for local component style
  props (e.g. `className`) before adding new global styles.

Vitest contains component-level assertions for the shadcn primitives. When
adding a new UI element, cover at least one render path inside `__tests__` to
protect the integration.

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
