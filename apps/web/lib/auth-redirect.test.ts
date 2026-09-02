import { describe, expect, it } from "vitest";
import { safeNext, withNext } from "./auth-redirect";

describe("safeNext", () => {
  it("keeps same-site paths", () => {
    expect(safeNext("/invite/abc123")).toBe("/invite/abc123");
    expect(safeNext("/app/settings?tab=members")).toBe("/app/settings?tab=members");
  });

  it("falls back to /app when nothing was asked for", () => {
    expect(safeNext(null)).toBe("/app");
    expect(safeNext(undefined)).toBe("/app");
    expect(safeNext("")).toBe("/app");
  });

  it("refuses anything that could leave the site", () => {
    expect(safeNext("https://evil.example/")).toBe("/app");
    expect(safeNext("//evil.example/")).toBe("/app");
    expect(safeNext("/\\evil.example")).toBe("/app");
    expect(safeNext("javascript:alert(1)")).toBe("/app");
    expect(safeNext("/app\nSet-Cookie: x")).toBe("/app");
  });
});

describe("withNext", () => {
  it("carries a non-default destination, encoded", () => {
    expect(withNext("/login", "/invite/abc?x=1")).toBe("/login?next=%2Finvite%2Fabc%3Fx%3D1");
  });

  it("leaves the path bare for the default destination", () => {
    expect(withNext("/login", "/app")).toBe("/login");
    expect(withNext("/signup", "https://evil.example/")).toBe("/signup");
  });
});
