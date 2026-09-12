import { useEffect, useState } from "react";

/** Mount with a new key for each confirmed operation, including repeated saves. */
export function TransientNotice({ message }: { message: string }) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 5000);
    return () => window.clearTimeout(timer);
  }, []);
  return visible ? (
    <div
      className="admin-success-toast"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span aria-hidden="true">✓</span> {message}
    </div>
  ) : null;
}
