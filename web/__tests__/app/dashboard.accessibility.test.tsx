import {
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import { AuthProvider } from "@/app/providers";

function renderDashboard() {
  return render(
    <AuthProvider value={{ isAuthenticated: true }}>
      <DashboardPage />
    </AuthProvider>,
  );
}

function interactiveLabels() {
  const focusable = Array.from(
    document.querySelectorAll<HTMLElement>(
      "button, select, [tabindex]:not([tabindex='-1'])",
    ),
  );

  return focusable.map((element) => {
    const ariaLabel = element.getAttribute("aria-label");
    const label =
      ariaLabel?.trim() || element.textContent?.trim() || element.tagName;
    return label;
  });
}

describe("/dashboard accessibility", () => {
  it("exposes landmarks, labels, and chart semantics", async () => {
    renderDashboard();

    const main = screen.getByRole("main");
    expect(within(main).getByText(/environment/i)).toBeInTheDocument();

    expect(screen.getByLabelText(/dashboard base coin/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/dashboard quote coin/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/dashboard analytics window/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /swap coins/i }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("img", {
        name: /price and sentiment composed chart/i,
      }),
    ).toBeInTheDocument();
  });

  it("maintains keyboard-friendly focus order across selectors and widgets", () => {
    renderDashboard();

    const base = screen.getByLabelText(/dashboard base coin/i);
    const swap = screen.getByRole("button", { name: /swap coins/i });
    const quote = screen.getByLabelText(/dashboard quote coin/i);
    const analytics = screen.getByLabelText(/dashboard analytics window/i);
    const leader = screen.getByLabelText(/leader symbol/i);
    const follower = screen.getByLabelText(/follower symbol/i);
    const leadlagWindow = screen.getByLabelText(/lead\/lag window/i);

    const tabbables = Array.from(
      document.querySelectorAll<HTMLElement>(
        "button, select, [tabindex]:not([tabindex='-1'])",
      ),
    );

    const positions = [
      tabbables.indexOf(base),
      tabbables.indexOf(swap),
      tabbables.indexOf(quote),
      tabbables.indexOf(analytics),
      tabbables.indexOf(leader),
      tabbables.indexOf(follower),
      tabbables.indexOf(leadlagWindow),
    ];

    const sortedPositions = [...positions].sort((a, b) => a - b);
    expect(positions).toEqual(sortedPositions);
  });

  it("allows keyboard-driven state changes", async () => {
    renderDashboard();

    const analyticsWindow = screen.getByLabelText(
      /dashboard analytics window/i,
    );
    fireEvent.change(analyticsWindow, { target: { value: "4h" } });
    await waitFor(() => expect(analyticsWindow).toHaveValue("4h"));

    const swapButton = screen.getByRole("button", { name: /swap coins/i });
    swapButton.focus();
    fireEvent.keyDown(swapButton, { key: "Enter", code: "Enter" });
    fireEvent.keyUp(swapButton, { key: "Enter", code: "Enter" });
    fireEvent.click(swapButton);
    await waitFor(() =>
      expect(screen.getByLabelText(/dashboard base coin/i)).toHaveValue("ETH"),
    );
  });
});
