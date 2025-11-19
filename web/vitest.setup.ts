import "@testing-library/jest-dom/vitest";

import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "./vendor/msw/lib/node.js";

import { analyticsHandlers } from "./src/mocks/handlers/analytics";

export const server = setupServer(...analyticsHandlers);

beforeAll(() => {
  server.listen();
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
