import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import { AuthProvider } from "@/app/providers";

function renderDashboard() {
  return render(
    <AuthProvider value={{ isAuthenticated: true }}>
      <DashboardPage />
    </AuthProvider>,
  );
}

describe("/dashboard performance instrumentation", () => {
  beforeEach(() => {
    performance.clearMarks();
    performance.clearMeasures();
  });

  it("records load, swap, and window-change metrics", async () => {
    renderDashboard();

    await waitFor(() => {
      expect(performance.getEntriesByName("dashboard:load")).not.toHaveLength(
        0,
      );
    });

    const swapButton = screen.getByRole("button", { name: /swap coins/i });
    fireEvent.click(swapButton);
    await waitFor(() => {
      expect(performance.getEntriesByName("dashboard:swap")).not.toHaveLength(
        0,
      );
    });

    const analyticsWindow = screen.getByLabelText(
      /dashboard analytics window/i,
    );
    fireEvent.change(analyticsWindow, { target: { value: "4h" } });
    await waitFor(() => {
      expect(
        performance.getEntriesByName("dashboard:window-change"),
      ).not.toHaveLength(0);
    });
  });

  it("captures sentiment render performance", async () => {
    renderDashboard();

    await waitFor(() => {
      expect(
        performance.getEntriesByName("dashboard:sentiment:render"),
      ).not.toHaveLength(0);
    });
  });
});
