import { render, screen } from "@testing-library/react";

import { Button } from "@/components/ui";

describe("Button", () => {
  it("renders label text", () => {
    render(<Button>Click me</Button>);
    expect(
      screen.getByRole("button", { name: "Click me" }),
    ).toBeInTheDocument();
  });
});
