module.exports = {
  ci: {
    collect: {
      numberOfRuns: 3,
      startServerCommand: "pnpm start -- --hostname 0.0.0.0 --port 3000",
      startServerReadyPattern: "ready - started server|Ready in",
      url: ["http://localhost:3000/"],
      settings: {
        formFactor: "desktop",
        screenEmulation: { disabled: true },
        throttlingMethod: "simulate",
        throttling: {
          rttMs: 40,
          throughputKbps: 10240,
          cpuSlowdownMultiplier: 2,
          requestLatencyMs: 0,
          downloadThroughputKbps: 0,
          uploadThroughputKbps: 0,
        },
        maxWaitForLoad: 60000,
        maxWaitForFcp: 30000,
      },
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.85 }],
        "categories:accessibility": ["error", { minScore: 0.9 }],
      },
    },
    upload: {
      target: "filesystem",
      outputDir: ".lighthouseci",
    },
  },
};
