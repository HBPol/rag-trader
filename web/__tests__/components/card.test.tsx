import { render, screen } from "@testing-library/react";

import { CardFooter } from "@/components/ui/card";

describe("CardFooter", () => {
  it("combines default classes with provided className and renders children", () => {
    render(
      <CardFooter className="custom" data-testid="card-footer">
        Footer content
      </CardFooter>,
    );

    const footer = screen.getByTestId("card-footer");

    expect(footer).toHaveClass("flex");
    expect(footer).toHaveClass("items-center");
    expect(footer).toHaveClass("p-6");
    expect(footer).toHaveClass("pt-0");
    expect(footer).toHaveClass("custom");
    expect(screen.getByText("Footer content")).toBeInTheDocument();
  });
});
