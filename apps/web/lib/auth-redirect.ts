/** Where to send someone after they sign up, sign in, or confirm an email.
 *
 * The `next` value travels through query strings — the invite page sets it,
 * signup embeds it in the confirmation link, the auth callback reads it back.
 * Anything that isn't a same-site path is refused: an open redirect through
 * the auth callback would let a phishing link finish on someone else's site
 * with a real session freshly set. */

export const DEFAULT_AFTER_AUTH = "/app";

export function safeNext(value: string | null | undefined): string {
  if (!value) return DEFAULT_AFTER_AUTH;
  // Same-site paths only: must start with a single slash, and never with a
  // scheme-relative `//host` or a backslash that browsers normalise to one.
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return DEFAULT_AFTER_AUTH;
  }
  // No whitespace or control characters: they have no place in a path and
  // are the raw material of header-injection tricks.
  if (/\s/.test(value)) return DEFAULT_AFTER_AUTH;
  return value;
}

/** Append `next` to an auth page path, omitting it when it's the default. */
export function withNext(path: string, next: string): string {
  const safe = safeNext(next);
  return safe === DEFAULT_AFTER_AUTH ? path : `${path}?next=${encodeURIComponent(safe)}`;
}
