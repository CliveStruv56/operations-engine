"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "@/components/activity";
import { btnDanger, btnIcon, btnPrimary, btnQuiet, btnSecondary } from "./styles";

const VARIANTS = {
  primary: btnPrimary,
  secondary: btnSecondary,
  danger: btnDanger,
  quiet: btnQuiet,
  icon: btnIcon,
} as const;

export type ButtonVariant = keyof typeof VARIANTS;

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> & {
  variant?: ButtonVariant;
  /** Shows a spinner, blocks the click, and marks the control aria-busy. */
  loading?: boolean;
  /** Replaces the label while loading. Keep the width stable — no layout jump. */
  loadingLabel?: string;
  children?: ReactNode;
  className?: string;
};

/**
 * The one button. `type` defaults to "button" because a bare <button> inside a
 * form submits it, which is the most common accidental-submit bug in the app.
 *
 * Loading is a real state rather than a caller-managed `disabled`: a disabled
 * button announces "you cannot do this", while a busy one announces "this is
 * happening", and only the second is true mid-request.
 */
export function Button({
  variant = "primary",
  loading = false,
  loadingLabel,
  disabled,
  children,
  className = "",
  type = "button",
  ...rest
}: Props) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}
