import { vi } from "vitest";

describe("resolveDefaultAuthValue", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_AUTH_MOCK_STATE;
    vi.resetModules();
  });

  it.each<[
    boolean,
    string | undefined,
  ]>([
    [true, "authenticated"],
    [false, "locked"],
    [false, undefined],
  ])(
    "returns isAuthenticated=%s when NEXT_PUBLIC_AUTH_MOCK_STATE=%s",
    async (expected, mockState) => {
      if (mockState) {
        process.env.NEXT_PUBLIC_AUTH_MOCK_STATE = mockState;
      } else {
        delete process.env.NEXT_PUBLIC_AUTH_MOCK_STATE;
      }

      const { resolveDefaultAuthValue } = await import("@/app/providers");

      expect(resolveDefaultAuthValue().isAuthenticated).toBe(expected);
    },
  );
});
