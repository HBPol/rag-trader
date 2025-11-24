import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";

import EventCards from "@/app/dashboard/EventCards";
import { AuthContext } from "@/app/providers";
import { eventsResponse } from "@/mocks/handlers/analytics";

import { server } from "../../vitest.setup";

function renderWithProviders(ui: ReactNode, client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={{ isAuthenticated: true }}>
        {ui}
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("EventCards", () => {
  it("orders events from most to least recent", async () => {
    const unordered = {
      ...eventsResponse,
      data: [
        {
          ...eventsResponse.data[1],
          published_at: "2024-02-28T10:00:00Z",
        },
        {
          ...eventsResponse.data[2],
          published_at: "2024-03-03T08:00:00Z",
        },
        eventsResponse.data[0],
      ],
    };

    server.use(http.get("/events", () => HttpResponse.json(unordered)));

    renderWithProviders(<EventCards />);

    const cards = await screen.findAllByTestId("event-card");
    const orderedTitles = cards.map(
      (card) => within(card).getByRole("heading", { level: 3 }).textContent,
    );

    expect(orderedTitles).toEqual([
      unordered.data[1].title,
      unordered.data[2].title,
      unordered.data[0].title,
    ]);
  });

  it("renders accessible source links for each event", async () => {
    renderWithProviders(<EventCards />);

    const sourceLink = await screen.findByRole("link", {
      name: /Source: Ethereum ETF approved with accelerated timeline/i,
    });

    expect(sourceLink).toHaveAttribute("href", "https://example.com/eth-etf");
    expect(sourceLink).toHaveAccessibleName();
  });

  it("shows neutral badges when sentiment is missing", async () => {
    renderWithProviders(<EventCards />);

    const inflationCard = await screen.findByText(
      /Core inflation surprise sends risk assets lower/i,
    );

    const card = inflationCard.closest("li");
    expect(card).not.toBeNull();

    const badge = within(card as HTMLElement).getByLabelText(
      /Sentiment: No sentiment/i,
    );
    expect(badge).toHaveTextContent("N/A");
  });

  it("renders loading, empty, and error states", async () => {
    const slowResponse = new Promise((resolve) => setTimeout(resolve, 300));
    server.use(
      http.get("/events", async () => {
        await slowResponse;
        return HttpResponse.json(eventsResponse);
      }),
    );

    renderWithProviders(<EventCards />);

    expect(await screen.findByTestId("event-cards-loading")).toBeVisible();

    await screen.findAllByTestId("event-card");

    server.use(
      http.get("/events", () => HttpResponse.json({ status: "ok", data: [] })),
    );

    renderWithProviders(
      <EventCards />,
      new QueryClient({
        defaultOptions: { queries: { retry: false } },
      }),
    );

    await screen.findByText(/No events available yet/i);

    server.use(
      http.get("/events", () =>
        HttpResponse.json({ message: "feed unavailable" }, { status: 500 }),
      ),
    );

    renderWithProviders(
      <EventCards />,
      new QueryClient({
        defaultOptions: { queries: { retry: false } },
      }),
    );

    const alert = await screen.findByRole("alert", {
      name: "Events feed error",
    });
    expect(alert).toHaveTextContent(/feed unavailable/i);
  });
});
