import { createRef } from "react";
import { render, screen } from "@testing-library/react";

import { Input } from "@/components/ui";

describe("Input", () => {
  it("keeps the provided type and merges classes", () => {
    render(<Input type="email" className="extra" data-testid="input" />);

    const element = screen.getByTestId("input");

    expect(element).toHaveAttribute("type", "email");
    expect(element).toHaveClass("extra");
    expect(element).toHaveClass("flex");
  });

  it("forwards refs to the underlying DOM node", () => {
    const ref = createRef<HTMLInputElement>();

    render(<Input ref={ref} />);

    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it("applies disabled styling when disabled", () => {
    render(<Input disabled data-testid="disabled-input" />);

    const element = screen.getByTestId("disabled-input");

    expect(element).toBeDisabled();
    expect(element).toHaveClass("disabled:cursor-not-allowed");
    expect(element).toHaveClass("disabled:opacity-50");
  });
});
