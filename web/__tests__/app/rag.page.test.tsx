import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import RagPage from "@/app/rag/page";
import { ragResponseSchema } from "@/lib/schemas/rag";

import * as apiClient from "@/lib/api/client";

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

function renderWithClient() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <RagPage />
    </QueryClientProvider>,
  );
}

describe("RagPage", () => {
  const mockResponse = ragResponseSchema.parse({
    query: "test",
    summary: "Alpha thesis [1] and beta angle [2]",
    snippets: [
      {
        id: "a1",
        title: "Alpha",
        source: "unit",
        published_at: "2024-01-01T00:00:00Z",
        content: "Alpha body",
        citation: 1,
      },
      {
        id: "b2",
        title: "Beta",
        source: "unit",
        published_at: "2024-01-02T00:00:00Z",
        content: "Beta body",
        citation: 2,
      },
    ],
  });

  beforeEach(() => {
    vi.spyOn(apiClient, "apiFetch").mockResolvedValue(mockResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders query form and results", async () => {
    renderWithClient();

    const queryInput = screen.getByLabelText("Query");
    fireEvent.change(queryInput, { target: { value: "How is BTC doing?" } });

    fireEvent.click(screen.getByRole("button", { name: /run retrieval/i }));

    await waitFor(() =>
      expect(screen.getByText(/Alpha thesis/)).toBeInTheDocument(),
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(apiClient.apiFetch).toHaveBeenCalledWith(
      "/rag",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("links citations back to snippets", async () => {
    renderWithClient();

    fireEvent.click(screen.getByRole("button", { name: /run retrieval/i }));

    const citationLink = await screen.findByRole("link", {
      name: /jump to source 1/i,
    });
    expect(citationLink).toHaveAttribute("href", "#snippet-1");
    expect(screen.getByText("Citation [1]")).toBeInTheDocument();
  });
});
