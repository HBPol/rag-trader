import type { HttpHandler } from "./index.js";

export interface SetupServerApi {
  listen: () => void;
  close: () => void;
  resetHandlers: (...nextHandlers: HttpHandler[]) => void;
  use: (...nextHandlers: HttpHandler[]) => void;
}

export function setupServer(...handlers: HttpHandler[]): SetupServerApi;
