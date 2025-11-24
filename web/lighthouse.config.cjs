module.exports = {
  ci: {
    collect: {
      numberOfRuns: 1,
      startServerCommand: "pnpm start -- --hostname 0.0.0.0 --port 3000",
      startServerReadyPattern: "ready - started server|Ready in",
      url: ["http://localhost:3000/"],
      settings: {
        formFactor: "desktop",
        screenEmulation: { disabled: true },
      },
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.85 }],
        "categories:accessibility": ["error", { minScore: 0.85 }],
      },
    },
    upload: {
      target: "filesystem",
      outputDir: ".lighthouseci",
    },
  },
};
