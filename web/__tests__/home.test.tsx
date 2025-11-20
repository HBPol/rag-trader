import { render, screen } from "@testing-library/react";

import { AuthProvider } from "../src/app/providers";
import Home from "../src/app/page";

describe("Home page scaffold", () => {
  it("renders the marketing shell publicly", () => {
    render(<Home />);

    expect(screen.getByText("RAGTrader")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Monorepo scaffold ready. Subsequent tasks will bring live price and sentiment analytics to life.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "You are signed in via the mock auth provider—swap the environment flag to review the locked experience.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Sign in to unlock market insights/i),
    ).not.toBeInTheDocument();
  });

  it("keeps the CTA pointing to the dashboard", () => {
    render(<Home />);

    const cta = screen.getByRole("link", { name: /enter dashboard/i });
    expect(cta).toHaveAttribute("href", "/dashboard");
  });

  it("does not require authentication context to render", () => {
    render(
      <AuthProvider value={{ isAuthenticated: false }}>
        <Home />
      </AuthProvider>,
    );

    expect(screen.getByText("RAGTrader")).toBeInTheDocument();
  });
});
