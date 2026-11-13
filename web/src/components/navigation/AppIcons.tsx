/*
 * Colorful, filled shortcut icons in the style of Facebook's left sidebar.
 * Original drawings for this prototype (Meta's own artwork is not bundled).
 * Same props as lucide icons (size, className) so they drop into the nav.
 */
import { useId, type ReactNode } from "react";

export interface AppIconProps {
  size?: number;
  className?: string;
}

type Stops = [string, string];

function Svg({ size = 36, className, children }: AppIconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 36 36"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Unique gradient ids per rendered icon. */
function useGrad(count: number) {
  const base = useId().replace(/:/g, "");
  return Array.from({ length: count }, (_, i) => `${base}g${i}`);
}

function Linear({ id, stops, x2 = 0, y2 = 1 }: { id: string; stops: Stops; x2?: number; y2?: number }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2={x2} y2={y2}>
      <stop offset="0" stopColor={stops[0]} />
      <stop offset="1" stopColor={stops[1]} />
    </linearGradient>
  );
}

export function FriendsIcon(props: AppIconProps) {
  const [a, b] = useGrad(2);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#4fa3ff", "#1661e8"]} />
        <Linear id={b} stops={["#9cebdc", "#52c7b5"]} />
      </defs>
      <circle cx="24.5" cy="11.5" r="5" fill={`url(#${b})`} />
      <path d="M16 29c0-5.3 3.8-9.5 8.5-9.5S33 23.7 33 29v1.2c0 .7-.6 1.3-1.3 1.3H17.3c-.7 0-1.3-.6-1.3-1.3z" fill={`url(#${b})`} />
      <circle cx="13" cy="11" r="6" fill={`url(#${a})`} />
      <path d="M2.5 29.5C2.5 23.4 7.2 18.5 13 18.5s10.5 4.9 10.5 11V31c0 .8-.7 1.5-1.5 1.5H4c-.8 0-1.5-.7-1.5-1.5z" fill={`url(#${a})`} />
    </Svg>
  );
}

export function MemoriesIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#5cb8ff", "#1673e6"]} />
      </defs>
      <circle cx="19" cy="19" r="14.5" fill={`url(#${a})`} />
      <circle cx="19" cy="19" r="11" fill="#fff" />
      <path d="M19 12v7.5l5 3" fill="none" stroke="#1c2b33" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2.5 5.5 3 13l7.2-1.9z" fill="#1673e6" />
    </Svg>
  );
}

export function SavedIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#d53a9d", "#7b5cf5"]} />
      </defs>
      <path d="M8 5.5A2.5 2.5 0 0 1 10.5 3h15A2.5 2.5 0 0 1 28 5.5v26.2c0 .9-1 1.4-1.7.9L18 26.6l-8.3 6c-.7.5-1.7 0-1.7-.9z" fill={`url(#${a})`} />
    </Svg>
  );
}

export function GroupsIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#4fa3ff", "#1661e8"]} />
      </defs>
      <circle cx="18" cy="18" r="17" fill={`url(#${a})`} />
      <g fill="#fff">
        <circle cx="18" cy="12.5" r="3.6" />
        <path d="M11.5 25.5c0-3.9 2.9-7 6.5-7s6.5 3.1 6.5 7v.5c0 .6-.4 1-1 1h-11c-.6 0-1-.4-1-1z" />
        <circle cx="9.6" cy="15.2" r="2.7" />
        <path d="M4.8 25c0-3 2.1-5.3 4.8-5.3 1 0 1.9.3 2.6.8-1 1.4-1.6 3.1-1.7 5H5.6c-.4 0-.8-.3-.8-.5z" />
        <circle cx="26.4" cy="15.2" r="2.7" />
        <path d="M31.2 25c0-3-2.1-5.3-4.8-5.3-1 0-1.9.3-2.6.8 1 1.4 1.6 3.1 1.7 5h4.9c.4 0 .8-.3.8-.5z" />
      </g>
    </Svg>
  );
}

export function ConstellationsIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#3b6cff", "#a440e0"]} x2={1} />
      </defs>
      <circle cx="18" cy="18" r="17" fill={`url(#${a})`} />
      <g stroke="#fff" strokeWidth="1.5" strokeLinecap="round" opacity="0.85">
        <line x1="9.5" y1="22.5" x2="15.5" y2="12" />
        <line x1="15.5" y1="12" x2="24" y2="15.5" />
        <line x1="24" y1="15.5" x2="27" y2="25" />
        <line x1="9.5" y1="22.5" x2="18" y2="26.5" />
      </g>
      <g fill="#fff">
        <circle cx="9.5" cy="22.5" r="2.2" />
        <circle cx="15.5" cy="12" r="2.8" />
        <circle cx="24" cy="15.5" r="2.2" />
        <circle cx="27" cy="25" r="1.9" />
        <circle cx="18" cy="26.5" r="1.9" />
      </g>
    </Svg>
  );
}

export function VideoIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#ff8a4c", "#e8407a"]} x2={0.6} />
      </defs>
      <rect x="3" y="3" width="30" height="30" rx="8" fill={`url(#${a})`} />
      <path d="M3 11h30" stroke="#fff" strokeWidth="1.6" opacity="0.9" />
      <path d="m10 3.5 4.5 7.5M18 3.5l4.5 7.5M26 3.5l4.5 7.5" stroke="#fff" strokeWidth="1.6" opacity="0.9" />
      <path d="M15 16.5v10.6c0 .8.9 1.3 1.6.8l7.6-5.3c.6-.4.6-1.2 0-1.6l-7.6-5.3c-.7-.5-1.6 0-1.6.8z" fill="#fff" />
    </Svg>
  );
}

export function MarketplaceIcon(props: AppIconProps) {
  const [a, b] = useGrad(2);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#4fa3ff", "#1661e8"]} />
        <Linear id={b} stops={["#7cc6ff", "#3b8cf5"]} />
      </defs>
      <rect x="5.5" y="15" width="25" height="18" rx="2" fill={`url(#${a})`} />
      <rect x="14" y="21" width="8" height="12" rx="1" fill="#fff" />
      <path d="M6.2 4h23.6l3.7 9.2c.6 1.6-.6 3.3-2.3 3.3H4.8c-1.7 0-2.9-1.7-2.3-3.3z" fill={`url(#${b})`} />
      <path d="M12 4 10 16.5M18 4v12.5M24 4l2 12.5" stroke="#fff" strokeWidth="1.4" opacity="0.7" />
    </Svg>
  );
}

export function EventsIcon(props: AppIconProps) {
  return (
    <Svg {...props}>
      <rect x="4" y="5" width="28" height="27" rx="4" fill="#fff" stroke="#dadde1" />
      <path d="M4 9a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v3.5H4z" fill="#e8344e" />
      <path d="m18 15.8 1.9 3.9 4.3.6-3.1 3 .7 4.3-3.8-2-3.8 2 .7-4.3-3.1-3 4.3-.6z" fill="#3a3b3c" />
    </Svg>
  );
}

export function FeedsIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#5cb8ff", "#1673e6"]} />
      </defs>
      <rect x="3" y="4" width="28" height="20" rx="3" fill="#fff" stroke="#dadde1" />
      <rect x="3" y="14" width="28" height="10" rx="0" fill={`url(#${a})`} />
      <circle cx="8" cy="9" r="2" fill="#1673e6" />
      <rect x="12" y="7.8" width="14" height="2.4" rx="1.2" fill="#8a8d91" />
      <circle cx="24" cy="25" r="7.5" fill="#fff" stroke="#1c2b33" strokeWidth="2" />
      <path d="M24 21v4.2l2.6 1.6" fill="none" stroke="#1c2b33" strokeWidth="2" strokeLinecap="round" />
    </Svg>
  );
}

export function MessengerIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#2f8cff", "#a83cf0"]} x2={0.7} />
      </defs>
      <path d="M18 3C9.7 3 3 9.2 3 16.8c0 4.2 2 7.9 5.2 10.4V33l5.4-3c1.4.4 2.9.6 4.4.6 8.3 0 15-6.2 15-13.8S26.3 3 18 3z" fill={`url(#${a})`} />
      <g fill="#fff">
        <circle cx="11.5" cy="17" r="2" />
        <circle cx="18" cy="17" r="2" />
        <circle cx="24.5" cy="17" r="2" />
      </g>
    </Svg>
  );
}

export function AiIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} stops={["#4f7bff", "#c247e0"]} x2={1} />
      </defs>
      <path d="M17 3c.9 6.7 4.3 10.1 11 11-6.7.9-10.1 4.3-11 11-.9-6.7-4.3-10.1-11-11 6.7-.9 10.1-4.3 11-11z" fill={`url(#${a})`} />
      <path d="M28 21c.5 3.4 2.1 5 5.5 5.5-3.4.5-5 2.1-5.5 5.5-.5-3.4-2.1-5-5.5-5.5 3.4-.5 5-2.1 5.5-5.5z" fill={`url(#${a})`} />
    </Svg>
  );
}
