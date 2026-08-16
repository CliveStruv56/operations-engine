import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from "react";
import { th as thCls } from "./styles";

/**
 * Table shell. The horizontal scroll is tabbable so a keyboard user can reach
 * the overflowing columns — a plain `overflow-x-auto` div traps them.
 */
export function Table({
  label,
  children,
  className = "",
}: {
  /** Names the table for screen readers. Tables are not self-describing. */
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div tabIndex={0} className="-mx-1 overflow-x-auto px-1">
      <table aria-label={label} className={`w-full text-sm ${className}`}>
        {children}
      </table>
    </div>
  );
}

/**
 * Header cell. `scope="col"` is the default rather than an option, because it
 * was missing from every table in the app and there is no case here for a
 * header cell that scopes to nothing.
 */
export function Th({
  numeric = false,
  className = "",
  children,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <th
      scope="col"
      className={`${thCls} font-bold ${numeric ? "text-right" : ""} ${className}`}
      {...rest}
    >
      {children}
    </th>
  );
}

/** Row header — the cell that identifies the row, e.g. a name or a model. */
export function Tr({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <tr className={`border-b border-edge last:border-0 ${className}`}>{children}</tr>
  );
}

/**
 * Body cell. `numeric` right-aligns and switches on tabular figures so digits
 * line up down the column — without it, proportional numerals make a money
 * column look ragged even when the values are the same width.
 */
export function Td({
  numeric = false,
  className = "",
  children,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <td
      className={`px-4 py-2.5 ${numeric ? "tnum text-right" : ""} ${className}`}
      {...rest}
    >
      {children}
    </td>
  );
}
