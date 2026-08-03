import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);

// next/navigation has no router outside the App Router runtime, so every
// component test would otherwise blow up on useRouter(). Tests that care what
// was navigated to assert against these.
export const routerMock = {
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

afterEach(() => {
  Object.values(routerMock).forEach((fn) => fn.mockClear());
});
