import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("@/app/providers", () => ({
  AppProviders: ({ children }: { children: ReactNode }) => (
    <div data-testid="app-providers">{children}</div>
  ),
}));

type LayoutModule = typeof import("../../src/app/dashboard/layout");
let DashboardLayout: LayoutModule["default"];

beforeAll(async () => {
  const layoutModule: LayoutModule = await import(
    "../../src/app/dashboard/layout"
  );
  DashboardLayout = layoutModule.default;
});

describe("DashboardLayout", () => {
  it("wraps children with AppProviders", () => {
    const childText = "Dashboard content";

    render(
      <DashboardLayout>
        <span>{childText}</span>
      </DashboardLayout>,
    );

    const provider = screen.getByTestId("app-providers");
    expect(provider).toBeInTheDocument();
    expect(screen.getByText(childText)).toBeInTheDocument();
  });
});
