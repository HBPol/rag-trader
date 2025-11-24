const path = require("path");
const configPath = path.join(__dirname, "..", "lighthouse.config.cjs");
// eslint-disable-next-line @typescript-eslint/no-var-requires
const config = require(configPath);

const performanceScore =
  config.ci?.assert?.assertions?.["categories:performance"]?.[1]?.minScore ?? 0;
const accessibilityScore =
  config.ci?.assert?.assertions?.["categories:accessibility"]?.[1]?.minScore ??
  0;

if (performanceScore < 0.85 || accessibilityScore < 0.85) {
  console.error(
    "Lighthouse thresholds must stay at or above 0.85 for performance and accessibility.",
  );
  process.exit(1);
}

console.info("Lighthouse thresholds satisfy >=0.85 requirements.");
