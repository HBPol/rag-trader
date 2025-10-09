import { afterEach, describe, expect, it, vi } from "vitest";
import animate from "tailwindcss-animate";

const loadModule = async <T>(path: string): Promise<T> => {
  const imported = await import(path);
  return (imported as { default?: T }).default ?? (imported as T);
};

afterEach(() => {
  vi.resetModules();
});

describe("Project configuration", () => {
  it("exposes the expected Next.js config", async () => {
    const nextConfig =
      await loadModule<Record<string, unknown>>("../next.config.js");

    expect(nextConfig).toHaveProperty("reactStrictMode", true);
    expect(nextConfig).toHaveProperty("experimental");
    expect(
      (nextConfig as { experimental?: { typedRoutes?: boolean } }).experimental
        ?.typedRoutes,
    ).toBe(true);
  });

  it("registers PostCSS plugins for Tailwind and autoprefixer", async () => {
    const postcssConfig = await loadModule<{
      plugins: Record<string, unknown>;
    }>("../postcss.config.js");

    expect(postcssConfig.plugins).toBeDefined();
    expect(postcssConfig.plugins).toHaveProperty("tailwindcss");
    expect(postcssConfig.plugins).toHaveProperty("autoprefixer");
  });

  it("configures Tailwind with the expected globs and plugins", async () => {
    const tailwindConfig = await loadModule<{
      content: string[];
      plugins: unknown[];
    }>("../tailwind.config");

    expect(tailwindConfig.content).toEqual(
      expect.arrayContaining([
        "./src/app/**/*.{ts,tsx}",
        "./src/components/**/*.{ts,tsx}",
        "./src/**/*.{ts,tsx}",
        "./__tests__/**/*.{ts,tsx}",
      ]),
    );

    expect(tailwindConfig.plugins).toContain(animate);
  });
});
