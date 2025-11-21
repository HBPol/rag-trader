const DEFAULT_API_BASE_URL = "http://localhost:8000";

export type ApiClientOptions = RequestInit & {
  baseUrl?: string;
  throwOnError?: boolean;
};

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiClientOptions = {},
): Promise<T> {
  const { baseUrl, throwOnError = true, ...init } = options;
  const resolvedBaseUrl = (
    baseUrl ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    process.env.API_BASE_URL
  )?.replace(/\/$/, "");
  const target = `${resolvedBaseUrl || DEFAULT_API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const response = await fetch(target, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const message = await safeExtractError(response);
    const error = new Error(
      `Request failed with status ${response.status}${message ? `: ${message}` : ""}`,
    );
    Object.assign(error, { status: response.status, response });

    if (throwOnError) {
      throw error;
    }

    return Promise.reject(error);
  }

  return response.json() as Promise<T>;
}

async function safeExtractError(response: Response): Promise<string | null> {
  try {
    const payload = await response.json();
    if (payload && typeof payload === "object" && "message" in payload) {
      const message = (payload as { message?: unknown }).message;
      if (typeof message === "string") {
        return message;
      }
    }
  } catch (error) {
    console.warn("Unable to parse error response", error);
  }
  return response.statusText || null;
}
