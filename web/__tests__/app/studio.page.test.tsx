import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import StudioPage from "@/app/studio/page";
import { AppProviders } from "@/app/providers";
import { server } from "../../vitest.setup";

const renderPage = () =>
  render(
    <AppProviders value={{ isAuthenticated: true }}>
      <StudioPage />
    </AppProviders>,
  );

describe("StudioPage", () => {
  it("lets users render DSL and run backtests", async () => {
    renderPage();

    expect(screen.getByText(/educational use only/i)).toBeInTheDocument();

    const promptInput = screen.getByLabelText(/natural language prompt/i);
    fireEvent.change(promptInput, {
      target: { value: "mean reversion with volatility guard" },
    });

    fireEvent.click(screen.getByRole("button", { name: /render dsl/i }));

    await screen.findByDisplayValue(/MEAN_REVERSION_ENTRY/i);
    await screen.findByText(/Mean reversion leg with volatility guard/i);

    fireEvent.click(screen.getByRole("button", { name: /run backtest/i }));

    await waitFor(() => {
      expect(screen.getByText(/total return/i)).toBeInTheDocument();
      expect(screen.getByText(/5.10%/)).toBeInTheDocument();
      expect(screen.getByText(/Sharpe/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(
        screen.queryByText(/Run a backtest to populate equity marks/i),
      ).toBeNull();
      expect(
        screen.queryByText(
          /Drawdown timeline will appear after running a backtest/i,
        ),
      ).toBeNull();
    });

    await screen.findByText(/Gross exposure across the sample period/i);
  });

  it("surfaces API errors for DSL generation and backtests", async () => {
    server.use(
      http.post("/studio/dsl", () =>
        HttpResponse.json({ message: "Bad prompt" }, { status: 500 }),
      ),
    );

    renderPage();

    fireEvent.change(screen.getByLabelText(/natural language prompt/i), {
      target: { value: "bad prompt" },
    });

    fireEvent.click(screen.getByRole("button", { name: /render dsl/i }));

    await screen.findByText(/Bad prompt/);

    server.use(
      http.post("/studio/backtest", () =>
        HttpResponse.json({ message: "Backtest failed" }, { status: 500 }),
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /run backtest/i }));

    await screen.findByText(/Backtest failed/);
  });
});
