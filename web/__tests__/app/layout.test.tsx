import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("@/app/providers", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => (
    <div data-testid="auth-provider">{children}</div>
  ),
}));

type LayoutModule = typeof import("../../src/app/layout");
let RootLayout: LayoutModule["default"];
let metadataExport: LayoutModule["metadata"];

beforeAll(async () => {
  const layoutModule: LayoutModule = await import("../../src/app/layout");
  RootLayout = layoutModule.default;
  metadataExport = layoutModule.metadata;
});

describe("RootLayout", () => {
  it("renders the html language attribute, body classes, and wraps children in the AuthProvider", () => {
    const childText = "Sample child content";
    const { container } = render(
      <RootLayout>
        <span>{childText}</span>
      </RootLayout>,
    );

    const htmlElement = container.querySelector("html");
    expect(htmlElement).toHaveAttribute("lang", "en");

    const bodyElement = container.querySelector("body");
    expect(bodyElement).toHaveClass(
      "min-h-screen",
      "bg-background",
      "font-sans",
      "antialiased",
      "text-foreground",
    );

    const provider = screen.getByTestId("auth-provider");
    expect(within(provider).getByText(childText)).toBeInTheDocument();
  });

  it("exposes the expected metadata", () => {
    expect(metadataExport.title).toBe("RAGTrader");
    expect(metadataExport.description).toBe("Retrieve. Reason. Trade.");
  });
});
