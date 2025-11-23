module.exports = {
  extends: ["next/core-web-vitals"],
  ignorePatterns: ["e2e/**/*", "playwright.config.ts"],
  rules: {
    "no-console": ["warn", { allow: ["info", "warn", "error"] }],
  },
};
