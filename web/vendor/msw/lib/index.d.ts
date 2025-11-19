export interface HttpResponseInit extends ResponseInit {}

export class HttpResponse extends Response {
  static json<T>(body: T, init?: HttpResponseInit): HttpResponse;
}

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
export type HandlerResolver = (req: Request) => Response | Promise<Response>;
export interface HttpHandler {
  method: HttpMethod;
  path: string;
  resolver: HandlerResolver;
}

export interface HttpInterface {
  get: (path: string, resolver: HandlerResolver) => HttpHandler;
  post: (path: string, resolver: HandlerResolver) => HttpHandler;
  put: (path: string, resolver: HandlerResolver) => HttpHandler;
  delete: (path: string, resolver: HandlerResolver) => HttpHandler;
  patch: (path: string, resolver: HandlerResolver) => HttpHandler;
}

export const http: HttpInterface;
