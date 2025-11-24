module.exports = {
  extends: ["next/core-web-vitals"],
  ignorePatterns: [
    "e2e/**/*",
    "playwright.config.ts",
    "next.config.js",
    "postcss.config.js",
    "tools/**/*",
    "vendor/**/*",
  ],
  rules: {
    "no-console": ["warn", { allow: ["info", "warn", "error"] }],
  },
};
