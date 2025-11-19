import { HttpResponse } from "./index.js";

function matchesPath(requestUrl, handlerPath) {
  if (!handlerPath) return false;
  const url = new URL(requestUrl);
  const normalizedPath = handlerPath.startsWith("http")
    ? new URL(handlerPath).pathname
    : handlerPath;
  return url.pathname === normalizedPath;
}

export function setupServer(...initialHandlers) {
  let handlers = [...initialHandlers];
  let originalFetch = null;

  const mockFetch = async (input, init) => {
    const request = new Request(input, init);
    const method = request.method.toUpperCase();
    const handler = handlers.find(
      (candidate) =>
        candidate.method === method && matchesPath(request.url, candidate.path),
    );

    if (!handler) {
      return HttpResponse.json(
        { message: `Unhandled ${method} ${new URL(request.url).pathname}` },
        { status: 500 },
      );
    }

    return handler.resolver(request);
  };

  return {
    listen() {
      if (!originalFetch) {
        originalFetch = globalThis.fetch;
        globalThis.fetch = mockFetch;
      }
    },
    close() {
      if (originalFetch) {
        globalThis.fetch = originalFetch;
        originalFetch = null;
      }
    },
    resetHandlers(...nextHandlers) {
      handlers = nextHandlers.length > 0 ? [...nextHandlers] : [...initialHandlers];
    },
    use(...nextHandlers) {
      handlers.push(...nextHandlers);
    },
  };
}
