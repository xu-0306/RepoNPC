import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

type Props = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "children"
> & {
  children: ReactNode;
  labelClassName?: string;
};

/** One native checkbox and one wrapping label, shared by every admin choice. */
export function CheckboxField({
  children,
  labelClassName = "",
  id,
  ...input
}: Props) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return (
    <label
      className={`checkbox-field ${labelClassName}`.trim()}
      htmlFor={inputId}
    >
      <input {...input} id={inputId} type="checkbox" />
      <span className="checkbox-field__text">{children}</span>
    </label>
  );
}
