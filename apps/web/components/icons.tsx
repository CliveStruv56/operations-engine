/** Shared 24-viewBox stroke icons (Hearth line style). Size via className. */

type IconProps = { className?: string };

function Icon({ children, className = "h-4 w-4" }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      {children}
    </svg>
  );
}

export function SearchIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Icon>
  );
}

export function ChatIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" />
    </Icon>
  );
}

export function VaultIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M4 7h16v13H4z" />
      <path d="M8 7V4h8v3" />
      <path d="M9.5 12h5" />
    </Icon>
  );
}

export function PulseIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M3 12h4l2-7 4 14 2-7h6" />
    </Icon>
  );
}

export function TargetIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="3.5" />
    </Icon>
  );
}

export function HomeIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M3 11 12 4l9 7" />
      <path d="M5 10v10h14V10" />
    </Icon>
  );
}

export function PeopleIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M16 5.5a3.5 3.5 0 0 1 0 5" />
      <path d="M17.5 14.5c2.1.8 3.5 2.9 3.5 5.5" />
    </Icon>
  );
}

export function DocIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M6 3h9l4 4v14H6z" />
      <path d="M14 3v5h5" />
    </Icon>
  );
}

export function GlobeIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a13.5 13.5 0 0 1 0 18 13.5 13.5 0 0 1 0-18Z" />
    </Icon>
  );
}

export function ArrowUpIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M12 19V5" />
      <path d="m5 12 7-7 7 7" />
    </Icon>
  );
}

export function PlusIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  );
}

export function PenIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <path d="m17 3 4 4L8 20l-5 1 1-5L17 3Z" />
    </Icon>
  );
}

export function CopyIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </Icon>
  );
}

export function StopIcon(p: IconProps) {
  return (
    <Icon {...p}>
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />
    </Icon>
  );
}
