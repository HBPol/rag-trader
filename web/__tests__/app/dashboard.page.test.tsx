import { render, screen } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import { AuthProvider } from "@/app/providers";

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
