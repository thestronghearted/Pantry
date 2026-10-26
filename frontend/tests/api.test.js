import { describe, expect, it, vi } from "vitest";
import { ApiError, getTraceId, onTraceId, request } from "../src/api.js";

const respond = (status, body, headers = {}) =>
  Promise.resolve(new Response(body === null ? null : JSON.stringify(body), { status, headers }));

describe("request", () => {
  it("sends JSON with same-origin credentials and returns the parsed body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => respond(200, { ok: true }));
    const data = await request("POST", "/api/x", { a: 1 });
    expect(data).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/x");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"a":1}');
  });

  it("remembers the trace id header and notifies listeners", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => respond(200, {}, { "X-Trace-Id": "abc123" }));
    const seen = vi.fn();
    const off = onTraceId(seen);
    await request("GET", "/api/x");
    off();
    expect(getTraceId()).toBe("abc123");
    expect(seen).toHaveBeenCalledWith("abc123");
  });

  it("turns string details into ApiError messages", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => respond(422, { detail: "No recipes fit those limits." }));
    await expect(request("POST", "/api/plan/generate", {})).rejects.toMatchObject({
      status: 422,
      message: "No recipes fit those limits.",
    });
  });

  it("flattens validation error lists", async () => {
    const detail = [{ loc: ["body", "age"], msg: "Input should be greater than or equal to 1" }];
    vi.spyOn(globalThis, "fetch").mockImplementation(() => respond(422, { detail }));
    await expect(request("POST", "/api/members", {})).rejects.toThrow("age: Input should be greater than or equal to 1");
  });

  it("hides server error internals", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => respond(500, { detail: "Internal server error" }));
    await expect(request("GET", "/api/x")).rejects.toThrow("Internal server error");
  });

  it("reports network failures as status 0", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await request("GET", "/api/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });

  it("returns null for 204", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })));
    expect(await request("POST", "/api/auth/logout")).toBeNull();
  });
});
