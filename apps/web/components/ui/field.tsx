"use client";

import { useId } from "react";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { input as inputCls, inputCompact, label as labelCls } from "./styles";

type FieldShell = {
  /** Always visible. A placeholder is not a label — it vanishes on the first
   *  keystroke, exactly when the user needs it most. */
  label: string;
  /** Standing guidance. Rendered before the error so the order never shifts. */
  hint?: ReactNode;
  /** Set after submit or on blur, never while the first character is typed. */
  error?: string | null;
  /** Most fields are required, so marking the rarer case is less noise. */
  optional?: boolean;
  className?: string;
};

/** Wires label, hint and error to the control by id so the whole group is
 *  announced together, and returns the ids the control needs. */
function useFieldIds(hint: ReactNode, error?: string | null) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return {
    id,
    hintId,
    errorId,
    describedBy: [hintId, errorId].filter(Boolean).join(" ") || undefined,
  };
}

function Shell({
  label,
  hint,
  error,
  optional,
  htmlFor,
  hintId,
  errorId,
  className = "",
  children,
}: FieldShell & {
  htmlFor: string;
  hintId?: string;
  errorId?: string;
  children: ReactNode;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className={labelCls}>
        {label}
        {optional && <span className="ml-1 lowercase tracking-normal">(optional)</span>}
      </label>
      {hint && (
        <p id={hintId} className="mb-1.5 text-xs text-subtle">
          {hint}
        </p>
      )}
      {children}
      {error && (
        <p id={errorId} className="mt-1.5 text-xs font-semibold text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

type InputProps = FieldShell &
  Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "id"> & {
    /** Row-height variant for tables and inline edits. */
    compact?: boolean;
  };

export function Input({
  label,
  hint,
  error,
  optional,
  compact,
  className,
  ...rest
}: InputProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(hint, error);
  return (
    <Shell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      htmlFor={id}
      hintId={hintId}
      errorId={errorId}
      className={className}
    >
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={compact ? inputCompact : inputCls}
        {...rest}
      />
    </Shell>
  );
}

type TextareaProps = FieldShell &
  Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className" | "id">;

export function Textarea({ label, hint, error, optional, className, ...rest }: TextareaProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(hint, error);
  return (
    <Shell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      htmlFor={id}
      hintId={hintId}
      errorId={errorId}
      className={className}
    >
      <textarea
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`${inputCls} min-h-20 resize-y`}
        {...rest}
      />
    </Shell>
  );
}

type SelectProps = FieldShell &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, "className" | "id"> & {
    children: ReactNode;
  };

export function Select({
  label,
  hint,
  error,
  optional,
  className,
  children,
  ...rest
}: SelectProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(hint, error);
  return (
    <Shell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      htmlFor={id}
      hintId={hintId}
      errorId={errorId}
      className={className}
    >
      <select
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={inputCls}
        {...rest}
      >
        {children}
      </select>
    </Shell>
  );
}
