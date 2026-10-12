import { afterEach, describe, expect, it, vi } from "vitest";
import { api, apiStream, ApiError } from "./api";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: async () => ({ data: { session: null } }) } }),
}));

function stubFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

function sse(...frames: string[]): Response {
  const body = new ReadableStream({
    start(controller) {
      for (const f of frames) controller.enqueue(new TextEncoder().encode(f));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

function handlers() {
  return { onDelta: vi.fn(), onDone: vi.fn(), onError: vi.fn(), onAbort: vi.fn() };
}

afterEach(() => vi.unstubAllGlobals());

/** The ApiError a call rejects with (fails the test if it resolves). */
async function rejection(p: Promise<unknown>): Promise<ApiError> {
  const err = await p.then(
    () => {
      throw new Error("expected a rejection");
    },
    (e: unknown) => e
  );
  expect(err).toBeInstanceOf(ApiError);
  return err as ApiError;
}

// WEB-3: a proxy's HTML error page is not JSON.
describe("api", () => {
  it("turns a non-JSON error page into an ApiError, not a parse error", async () => {
    stubFetch(async () => new Response("<html>Bad Gateway</html>", { status: 502 }));
    const err = await rejection(api("/x"));
    expect(err.status).toBe(502);
    expect(err.message).toContain("502");
  });

  it("keeps the API's own error message", async () => {
    stubFetch(async () =>
      Response.json({ error: { code: "signup_closed", message: "Ask your provider" } }, { status: 403 })
    );
    const err = await rejection(api("/x"));
    expect(err.code).toBe("signup_closed");
    expect(err.message).toBe("Ask your provider");
  });

  it("reports a network failure as an ApiError", async () => {
    stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const err = await rejection(api("/x"));
    expect(err.code).toBe("network");
  });

  it("accepts a JSON null body", async () => {
    stubFetch(async () => new Response("null", { status: 200 }));
    await expect(api("/x")).resolves.toBeNull();
  });
});

// WEB-2: every ending reaches exactly one handler, and nothing throws.
describe("apiStream", () => {
  it("reports a stream that ends without a done event", async () => {
    stubFetch(async () => sse('event: delta\ndata: {"content":"Hal"}\n\n'));
    const h = handlers();
    await apiStream("/s", {}, "t", h);
    expect(h.onDelta).toHaveBeenCalledWith("Hal");
    expect(h.onDone).not.toHaveBeenCalled();
    expect(h.onError).toHaveBeenCalledTimes(1);
    expect(h.onError.mock.calls[0][0]).toBe("stream_ended");
  });

  it("calls onDone once and nothing else on a clean stream", async () => {
    stubFetch(async () => sse('event: done\ndata: {"id":"m1"}\n\n'));
    const h = handlers();
    await apiStream("/s", {}, "t", h);
    expect(h.onDone).toHaveBeenCalledWith({ id: "m1" });
    expect(h.onError).not.toHaveBeenCalled();
  });

  it("reports a network failure instead of throwing", async () => {
    stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const h = handlers();
    await expect(apiStream("/s", {}, "t", h)).resolves.toBeUndefined();
    expect(h.onError).toHaveBeenCalledWith("network", expect.any(String));
  });

  it("reports an HTML error page through onError", async () => {
    stubFetch(async () => new Response("<html>502</html>", { status: 502 }));
    const h = handlers();
    await apiStream("/s", {}, "t", h);
    expect(h.onError).toHaveBeenCalledTimes(1);
    expect(h.onError.mock.calls[0][1]).toContain("502");
  });
});
