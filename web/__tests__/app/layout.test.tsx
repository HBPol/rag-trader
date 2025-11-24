import { render, screen } from "@testing-library/react";

type LayoutModule = typeof import("../../src/app/layout");
let RootLayout: LayoutModule["default"];
let metadataExport: LayoutModule["metadata"];

beforeAll(async () => {
  const layoutModule: LayoutModule = await import("../../src/app/layout");
  RootLayout = layoutModule.default;
  metadataExport = layoutModule.metadata;
});

describe("RootLayout", () => {
  it("renders the html language attribute, body classes, and children", () => {
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

    expect(screen.getByText(childText)).toBeInTheDocument();
    expect(screen.queryByTestId("auth-provider")).not.toBeInTheDocument();
  });

  it("exposes the expected metadata", () => {
    expect(metadataExport.title).toBe("RAGTrader");
    expect(metadataExport.description).toBe("Retrieve. Reason. Trade.");
  });
});
