import { render, screen } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import { AuthProvider } from "@/app/providers";
import { formatFreshness } from "@/app/dashboard/SentimentPriceChart";

const widgetPlaceholders = [
  "Market Heatmap",
  "Liquidity Funnels",
  "Custom Alerts",
  "Portfolio Blotter",
  "Retrieval Recipes",
  "Execution Quality",
];

describe("DashboardPage", () => {
  const renderWithAuth = (isAuthenticated: boolean) =>
    render(
      <AuthProvider value={{ isAuthenticated }}>
        <DashboardPage />
      </AuthProvider>,
    );

  it("renders dashboard content when authenticated", () => {
    renderWithAuth(true);

    expect(screen.getByText("Environment")).toBeInTheDocument();
    expect(screen.getByText(/Refreshed/i)).toBeInTheDocument();

    widgetPlaceholders.forEach((widget) => {
      expect(screen.getByText(widget)).toBeInTheDocument();
      expect(
        screen.getByText(
          new RegExp(`Placeholder for the ${widget.toLowerCase()}`, "i"),
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders locked copy when unauthenticated", () => {
    renderWithAuth(false);

    expect(
      screen.getByText(
        "Sign in to unlock market insights, watchlists, and custom retrieval workflows.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Authentication is coming soon—use the mocked auth flag while integration is in flight.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Environment")).not.toBeInTheDocument();
  });
});

describe("formatFreshness", () => {
  it("returns Unknown when age is missing or not finite", () => {
    expect(formatFreshness(undefined)).toBe("Unknown");
    expect(formatFreshness(null)).toBe("Unknown");
    expect(formatFreshness(Infinity)).toBe("Unknown");
  });

  it("formats sub-minute ages", () => {
    expect(formatFreshness(0.5)).toBe("<1 min ago");
  });

  it("formats minute-level ages under an hour", () => {
    expect(formatFreshness(5)).toBe("5.0 mins ago");
    expect(formatFreshness(59.9)).toBe("59.9 mins ago");
  });

  it("formats hour-level ages for values of an hour or more", () => {
    expect(formatFreshness(60)).toBe("1.0 hrs ago");
    expect(formatFreshness(120)).toBe("2.0 hrs ago");
  });
});
