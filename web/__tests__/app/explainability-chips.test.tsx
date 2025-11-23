import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";

import ExplainabilityChip from "@/app/dashboard/ExplainabilityChip";
import { explanationsResponse } from "@/mocks/handlers/analytics";

import { server } from "../../vitest.setup";

type WrapperProps = { client: QueryClient; children: ReactNode };

function Wrapper({ client, children }: WrapperProps) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("ExplainabilityChip", () => {
  it("lazily fetches explanations on hover and focus", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    let requestCount = 0;

    server.use(
      http.get("/explanations", () => {
        requestCount += 1;
        return HttpResponse.json(explanationsResponse);
      }),
    );

    const firstRender = render(
      <Wrapper client={client}>
        <ExplainabilityChip metricId="correlation:BTC:1h" label="Correlation" />
      </Wrapper>,
    );

    expect(requestCount).toBe(0);

    const button = screen.getByRole("button", { name: /Explain Correlation/i });
    fireEvent.mouseEnter(button);

    await waitFor(() => expect(requestCount).toBe(1));

    fireEvent.mouseLeave(button);
    fireEvent.focus(button);

    await waitFor(() => expect(requestCount).toBe(1));
  });

  it("reuses cached explanations across matching metric ids", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    let requestCount = 0;

    server.use(
      http.get("/explanations", () => {
        requestCount += 1;
        return HttpResponse.json(explanationsResponse);
      }),
    );

    render(
      <Wrapper client={client}>
        <ExplainabilityChip metricId="correlation:BTC:1h" label="Correlation" />
        <ExplainabilityChip
          metricId="correlation:BTC:1h"
          label="Correlation duplicate"
        />
      </Wrapper>,
    );

    const [first, second] = screen.getAllByRole("button", {
      name: /Explain Correlation/i,
    });

    fireEvent.mouseEnter(first);
    await waitFor(() => expect(requestCount).toBe(1));

    fireEvent.mouseEnter(second);
    await waitFor(() => expect(requestCount).toBe(1));
  });

  it("shows keyboard-focus tooltips with rationale and source", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const firstRender = render(
      <Wrapper client={client}>
        <ExplainabilityChip metricId="correlation:BTC:1h" label="Correlation" />
      </Wrapper>,
    );

    const button = screen.getByRole("button", { name: /Explain Correlation/i });
    fireEvent.focus(button);

    const rationale = await screen.findByText(
      explanationsResponse.data[0].rationale,
    );
    expect(rationale).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: explanationsResponse.data[0].source.label,
      }),
    ).toBeInTheDocument();
  });

  it("renders error and empty states", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    server.use(
      http.get("/explanations", () =>
        HttpResponse.json({ message: "boom" }, { status: 500 }),
      ),
    );

    const firstRender = render(
      <Wrapper client={client}>
        <ExplainabilityChip metricId="correlation:BTC:1h" label="Correlation" />
      </Wrapper>,
    );

    const button = screen.getByRole("button", { name: /Explain Correlation/i });
    fireEvent.focus(button);

    await screen.findByText(/Could not load rationale/i);
    expect(screen.getByText(/Explanation unavailable/i)).toBeInTheDocument();

    firstRender.unmount();

    server.use(
      http.get("/explanations", () =>
        HttpResponse.json({
          status: "ok",
          data: [{ id: "empty", rationale: null, source: null }],
        }),
      ),
    );

    const secondRender = render(
      <Wrapper client={client}>
        <ExplainabilityChip metricId="empty" label="Empty metric" />
      </Wrapper>,
    );

    const emptyButton = screen.getByRole("button", {
      name: /Explain Empty metric/i,
    });
    fireEvent.focus(emptyButton);

    await screen.findByText(/No explanation available yet/i);
    secondRender.unmount();
  });
});
