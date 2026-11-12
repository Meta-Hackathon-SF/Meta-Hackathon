import type { LucideIcon } from "lucide-react";

export default function NavigationIcon({
  icon: Icon,
  label,
  active,
  size = 26,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  size?: number;
}) {
  if (label === "Home" && active)
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        fill="none"
        aria-hidden="true"
      >
        <path
          fill="currentColor"
          d="M2 12.1c0-.9.4-1.8 1.1-2.3l9-7a3 3 0 0 1 3.8 0l9 7c.7.5 1.1 1.4 1.1 2.3v11.4a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3Z"
        />
        <path fill="white" d="M11 17a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v9.5h-6Z" />
      </svg>
    );
  return <Icon aria-hidden="true" size={size} strokeWidth={1.9} />;
}
