/** Shared activity indicators. Every busy state in the app was previously
 * static text; these make motion visible while respecting reduced-motion
 * (the spinner freezes into a partial ring, the dots fall back to "…"). */

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      className={`inline-block h-4 w-4 animate-spin align-[-0.2em] motion-reduce:animate-none ${className}`}
    >
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path
        d="M14.5 8a6.5 6.5 0 0 0-6.5-6.5"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function PulsingDots({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`} role="status" aria-label="Working">
      <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent motion-reduce:animate-none" />
      <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent [animation-delay:200ms] motion-reduce:animate-none" />
      <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent [animation-delay:400ms] motion-reduce:animate-none" />
    </span>
  );
}
