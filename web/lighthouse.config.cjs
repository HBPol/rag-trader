module.exports = {
  ci: {
    collect: {
      numberOfRuns: 1,
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
  },
};
