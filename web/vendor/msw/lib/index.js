class HttpResponse extends Response {
  static json(body, init = {}) {
    const headers = new Headers(init.headers ?? {});
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return new HttpResponse(JSON.stringify(body), { ...init, headers });
  }
}

function createHandler(method, path, resolver) {
  return { method: method.toUpperCase(), path, resolver };
}

const httpMethods = ["get", "post", "put", "delete", "patch"];

const http = httpMethods.reduce((api, method) => {
  api[method] = (path, resolver) => createHandler(method, path, resolver);
  return api;
}, {});

export { http, HttpResponse };
