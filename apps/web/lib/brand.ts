import type { CSSProperties } from "react";

function hexToRgb(hex: string): [number, number, number] | null {
  const m = /^#([0-9a-fA-F]{6})$/.exec(hex);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const toWhite = (c: number, ratio: number) => Math.round(c * (1 - ratio) + 255 * ratio);

/** Derive the accent CSS variables from a tenant's brand accent colour.
 * Soft is the accent washed nearly to white; ink flips black/white by
 * luminance — tenants pick one colour and cannot create unreadable pairs. */
export function deriveBrandVars(accent: unknown): CSSProperties | undefined {
  if (typeof accent !== "string") return undefined;
  const rgb = hexToRgb(accent);
  if (!rgb) return undefined;
  const [r, g, b] = rgb;
  const soft = `rgb(${toWhite(r, 0.92)}, ${toWhite(g, 0.92)}, ${toWhite(b, 0.92)})`;
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  const ink = luminance > 0.6 ? "#1c1e21" : "#ffffff";
  return {
    "--accent": accent,
    "--accent-soft": soft,
    "--accent-ink": ink,
  } as CSSProperties;
}
