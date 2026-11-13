/*
 * Colorful, filled icons in the style of Facebook's left sidebar, composer and
 * top tabs. Hand-drawn for this prototype to match Facebook's look; Meta's own
 * icon files are not bundled. Same props as lucide icons (size, className).
 */
import { useId, type ReactNode } from "react";

export interface AppIconProps {
  size?: number;
  className?: string;
}

function Svg({ size = 36, className, view = 36, children }: AppIconProps & { view?: number; children: ReactNode }) {
  return (
    <svg viewBox={`0 0 ${view} ${view}`} width={size} height={size} className={className} aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

/** Unique gradient ids per rendered icon. */
function useGrad(count: number) {
  const base = useId().replace(/:/g, "");
  return Array.from({ length: count }, (_, i) => `${base}g${i}`);
}

function Linear({ id, from, to, x1 = 0, y1 = 0, x2 = 0, y2 = 1 }: { id: string; from: string; to: string; x1?: number; y1?: number; x2?: number; y2?: number }) {
  return (
    <linearGradient id={id} x1={x1} y1={y1} x2={x2} y2={y2}>
      <stop offset="0" stopColor={from} />
      <stop offset="1" stopColor={to} />
    </linearGradient>
  );
}

/* ---- Left sidebar -------------------------------------------------------------- */

export function AiIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  const petals = 7;
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#c55cf2" to="#4c5df5" x1={0.2} y1={0} x2={0.6} y2={1} />
      </defs>
      <g fill={`url(#${a})`}>
        {Array.from({ length: petals }, (_, i) => {
          const angle = (i * 360) / petals - 90;
          const rad = (angle * Math.PI) / 180;
          const x = 18 + 11 * Math.cos(rad);
          const y = 18 + 11 * Math.sin(rad);
          return <ellipse key={i} cx={x} cy={y} rx="5.4" ry="3.7" transform={`rotate(${angle + 55} ${x} ${y})`} />;
        })}
      </g>
    </Svg>
  );
}

export function FriendsIcon(props: AppIconProps) {
  const [a, b] = useGrad(2);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#3e93f7" to="#1662e3" />
        <Linear id={b} from="#a3eadb" to="#5cc9b7" />
      </defs>
      <circle cx="24.5" cy="11" r="4.6" fill={`url(#${b})`} />
      <path d="M16.5 30.5c0-5.4 3.6-9.8 8-9.8s8 4.4 8 9.8v.3c0 .7-.6 1.2-1.2 1.2H17.7c-.7 0-1.2-.5-1.2-1.2z" fill={`url(#${b})`} />
      <circle cx="12.5" cy="11.5" r="5.6" fill={`url(#${a})`} />
      <path d="M2.5 30.8c0-6.4 4.5-11.3 10-11.3s10 4.9 10 11.3v.2c0 .8-.7 1.5-1.5 1.5H4c-.8 0-1.5-.7-1.5-1.5z" fill={`url(#${a})`} />
    </Svg>
  );
}

export function MemoriesIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  // Ring from the top-left end (with the back arrow) clockwise round to the left side.
  const r = 13;
  const at = (deg: number) => [19 + r * Math.cos((deg * Math.PI) / 180), 19 + r * Math.sin((deg * Math.PI) / 180)];
  const [sx, sy] = at(-128);
  const [ex, ey] = at(172);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#56b4ff" to="#1769e0" />
      </defs>
      <circle cx="19" cy="19" r="11" fill="#fff" />
      <path d={`M${sx} ${sy}A${r} ${r} 0 1 1 ${ex} ${ey}`} fill="none" stroke={`url(#${a})`} strokeWidth="4.2" strokeLinecap="round" />
      <path d="M2.6 4.6 3.4 14l8.6-3.2z" fill="#3d8ff0" />
      <path d="M17.4 11.6 19 19.4l4.6 4.4" fill="none" stroke="#1c2b33" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function SavedIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#d93f9a" to="#8b5cf5" />
      </defs>
      <path d="M9 5.2C9 3.4 10.4 2 12.2 2h11.6C25.6 2 27 3.4 27 5.2v27.3c0 .8-.9 1.3-1.6.8L18 28.4l-7.4 4.9c-.7.5-1.6 0-1.6-.8z" fill={`url(#${a})`} />
    </Svg>
  );
}

export function GroupsIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#55a6fb" to="#1864e4" />
      </defs>
      <circle cx="18" cy="18" r="17" fill={`url(#${a})`} />
      <g fill="#fff">
        <circle cx="18" cy="12.2" r="3.7" />
        <path d="M11.4 25.6c0-4 3-7.1 6.6-7.1s6.6 3.1 6.6 7.1v.4c0 .6-.4 1-1 1H12.4c-.6 0-1-.4-1-1z" />
        <circle cx="9.4" cy="15" r="2.8" />
        <path d="M4.4 25c0-3.1 2.2-5.5 5-5.5 1 0 2 .3 2.8.9-1.1 1.4-1.8 3.2-1.9 5.1H5.2c-.4 0-.8-.2-.8-.5z" />
        <circle cx="26.6" cy="15" r="2.8" />
        <path d="M31.6 25c0-3.1-2.2-5.5-5-5.5-1 0-2 .3-2.8.9 1.1 1.4 1.8 3.2 1.9 5.1h5.1c.4 0 .8-.2.8-.5z" />
      </g>
    </Svg>
  );
}

export function SpaceIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#3b6cff" to="#a440e0" x2={1} />
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
  const [a, b] = useGrad(2);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#f9a64c" to="#ee4a80" x1={0} y1={1} x2={1} y2={0} />
        <Linear id={b} from="#f45d84" to="#e8336f" x2={1} y2={0} />
      </defs>
      <rect x="3" y="3" width="30" height="30" rx="8" fill={`url(#${a})`} />
      <path d="M3 11V11C3 6.6 6.6 3 11 3h14c4.4 0 8 3.6 8 8z" fill={`url(#${b})`} />
      <path d="M3 11.2h30" stroke="#fff" strokeWidth="1.4" />
      <path d="m11.5 3.6 4.4 7.4M19.5 3.6l4.4 7.4M27.3 4.4l3.9 6.6" stroke="#fff" strokeWidth="1.8" />
      <path d="M15 16.8v9.6c0 1 1.1 1.6 1.9 1.1l7.3-4.8c.8-.5.8-1.6 0-2.1l-7.3-4.9c-.8-.5-1.9.1-1.9 1.1z" fill="#fff" />
    </Svg>
  );
}

export function MarketplaceIcon(props: AppIconProps) {
  const [a, b] = useGrad(2);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#3d8ff5" to="#1866e3" />
        <Linear id={b} from="#6ed6ee" to="#2d8ff0" x2={1} y2={0} />
      </defs>
      <path d="M5 15h26v15c0 1.7-1.3 3-3 3h-6.5v-8.5c0-.8-.7-1.5-1.5-1.5h-4c-.8 0-1.5.7-1.5 1.5V33H8c-1.7 0-3-1.3-3-3z" fill={`url(#${a})`} />
      <path d="M6.6 4h22.8c.9 0 1.6.6 1.9 1.4l2.4 7.6c.6 2-1 4-3.1 4-1.6 0-2.9-1-3.3-2.5-.4 1.5-1.8 2.5-3.3 2.5s-2.9-1-3.4-2.5c-.4 1.5-1.8 2.5-3.4 2.5s-2.9-1-3.3-2.5c-.4 1.5-1.7 2.5-3.3 2.5-2.1 0-3.7-2-3.1-4l2.4-7.6C5 4.6 5.7 4 6.6 4z" fill={`url(#${b})`} />
    </Svg>
  );
}

export function FeedsIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#5cb8ff" to="#1a73e8" />
      </defs>
      <rect x="2.5" y="4" width="31" height="22" rx="3.5" fill="#fff" stroke="#dfe1e5" strokeWidth="1" />
      <path d="M2.5 15h31v7.5c0 1.9-1.6 3.5-3.5 3.5H6c-1.9 0-3.5-1.6-3.5-3.5z" fill={`url(#${a})`} />
      <circle cx="8" cy="9.4" r="2.1" fill="#2d88f0" />
      <rect x="12.5" y="8.2" width="15" height="2.4" rx="1.2" fill="#8a8d91" />
      <circle cx="18" cy="26.5" r="7.2" fill="#fff" stroke="#1c2b45" strokeWidth="2" />
      <path d="M18 22.5v4.3l2.6 1.7" fill="none" stroke="#1c2b45" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function EventsIcon(props: AppIconProps) {
  return (
    <Svg {...props}>
      <rect x="4" y="4" width="28" height="28" rx="4" fill="#fff" stroke="#dadde1" />
      <path d="M4 8a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v4H4z" fill="#e8344e" />
      <path d="M4 12h28" stroke="#fff" strokeWidth="1" />
      <path d="M11 7.6h14" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" opacity="0.9" />
      <path d="m18 15.6 2 4 4.4.6-3.2 3.1.8 4.4-4-2.1-4 2.1.8-4.4-3.2-3.1 4.4-.6z" fill="#3a3b3c" />
    </Svg>
  );
}

export function MessengerIcon(props: AppIconProps) {
  const [a] = useGrad(1);
  return (
    <Svg {...props}>
      <defs>
        <Linear id={a} from="#2f8cff" to="#a83cf0" x2={0.7} />
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

/* ---- Composer ("What's on your mind?") ------------------------------------------- */

export function LiveVideoIcon(props: AppIconProps) {
  return (
    <Svg {...props} view={24}>
      <rect x="1" y="5" width="16" height="14" rx="3.6" fill="#f02849" />
      <path d="M18.2 9.6 21.7 7.5c.6-.4 1.3.1 1.3.8v7.4c0 .7-.7 1.2-1.3.8l-3.5-2.1z" fill="#f02849" />
      <path d="M3.8 12c1.3-2.4 3.1-3.6 5.2-3.6s3.9 1.2 5.2 3.6c-1.3 2.4-3.1 3.6-5.2 3.6S5.1 14.4 3.8 12z" fill="#fff" />
      <circle cx="9" cy="12" r="1.7" fill="#f02849" />
    </Svg>
  );
}

export function PhotoVideoIcon(props: AppIconProps) {
  return (
    <Svg {...props} view={24}>
      <rect x="1.5" y="1.5" width="16" height="16.5" rx="3" fill="#7fd08f" />
      <rect x="6" y="5.5" width="16.5" height="17" rx="3" fill="#45bd62" />
      <rect x="8.3" y="7.7" width="11.9" height="12.6" rx="1.6" fill="none" stroke="#fff" strokeWidth="1.4" />
      <circle cx="11.8" cy="11.2" r="1.5" fill="#fff" />
      <path d="m9 19.6 3.9-4.6 2.6 2.8 1.6-1.8 3 3.6z" fill="#fff" />
    </Svg>
  );
}

export function FeelingIcon(props: AppIconProps) {
  return (
    <Svg {...props} view={24}>
      <circle cx="12" cy="12" r="10" fill="none" stroke="#ec7a31" strokeWidth="2" />
      <ellipse cx="8.7" cy="9.4" rx="1.2" ry="1.6" fill="#ec7a31" />
      <ellipse cx="15.3" cy="9.4" rx="1.2" ry="1.6" fill="#ec7a31" />
      <path d="M7.2 13.2h9.6a4.8 4.8 0 0 1-9.6 0z" fill="#ec7a31" />
    </Svg>
  );
}

/* ---- Top tabs (outline when inactive, filled when active) ------------------------- */

export interface TabIconProps {
  size?: number;
  active?: boolean;
}

function Tab({ size = 28, children }: { size?: number; children: ReactNode }) {
  return (
    <svg viewBox="0 0 28 28" width={size} height={size} aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}

export function HomeTabIcon({ size, active }: TabIconProps) {
  const house = "M3 12.4c0-.9.4-1.7 1.1-2.3l8.1-6.6a2.9 2.9 0 0 1 3.6 0l8.1 6.6c.7.6 1.1 1.4 1.1 2.3V22a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z";
  return (
    <Tab size={size}>
      {active ? (
        <>
          <path d={house} fill="currentColor" stroke="none" />
          <path d="M11.5 25v-5.2c0-.9.7-1.6 1.6-1.6h1.8c.9 0 1.6.7 1.6 1.6V25z" fill="#fff" stroke="none" />
        </>
      ) : (
        <>
          <path d={house} />
          <path d="M11 25v-5c0-1.1.9-2 2-2h2c1.1 0 2 .9 2 2v5" />
        </>
      )}
    </Tab>
  );
}

export function FriendsTabIcon({ size, active }: TabIconProps) {
  const fill = active ? "currentColor" : "none";
  return (
    <Tab size={size}>
      <circle cx="10.5" cy="10" r="4" fill={fill} />
      <path d="M3 23c0-3.9 3.4-6.8 7.5-6.8S18 19.1 18 23v.3c0 .4-.3.7-.7.7H3.7c-.4 0-.7-.3-.7-.7z" fill={fill} />
      <circle cx="19.5" cy="7.5" r="3.3" fill={fill} />
      <path d="M17.6 14.3c.6-.2 1.3-.3 1.9-.3 3.3 0 6 2.4 6 5.6v.2c0 .4-.3.7-.7.7h-4.6" />
    </Tab>
  );
}

export function VideoTabIcon({ size, active }: TabIconProps) {
  return (
    <Tab size={size}>
      <rect x="3.5" y="3.5" width="21" height="21" rx="5.5" fill={active ? "currentColor" : "none"} />
      <path d="M3.5 10h21M10 3.8l3 6M16.5 3.8l3 6" stroke={active ? "#fff" : "currentColor"} />
      <path d="M12 13.6v6.3c0 .5.6.8 1 .5l4.6-3.1c.4-.3.4-.8 0-1.1L13 13.1c-.4-.3-1 0-1 .5z" fill={active ? "#fff" : "currentColor"} stroke="none" />
    </Tab>
  );
}

export function MarketplaceTabIcon({ size, active }: TabIconProps) {
  return (
    <Tab size={size}>
      <path d="M5.5 13v9a2.5 2.5 0 0 0 2.5 2.5h12a2.5 2.5 0 0 0 2.5-2.5v-9" fill={active ? "currentColor" : "none"} />
      <path d="M11 24.5v-4.3c0-.8.7-1.5 1.5-1.5h3c.8 0 1.5.7 1.5 1.5v4.3" stroke={active ? "#fff" : "currentColor"} />
      <path
        d="M4 10.2 5.5 5.3A2 2 0 0 1 7.4 4h13.2a2 2 0 0 1 1.9 1.3l1.5 4.9a2.6 2.6 0 0 1-2.5 3.3 2.7 2.7 0 0 1-2.5-1.6 2.7 2.7 0 0 1-2.5 1.6 2.7 2.7 0 0 1-2.5-1.6 2.7 2.7 0 0 1-2.5 1.6 2.7 2.7 0 0 1-2.5-1.6 2.7 2.7 0 0 1-2.5 1.6A2.6 2.6 0 0 1 4 10.2z"
        fill={active ? "currentColor" : "none"}
      />
    </Tab>
  );
}

export function GamingTabIcon({ size, active }: TabIconProps) {
  return (
    <Tab size={size}>
      <rect x="2.5" y="7.5" width="23" height="13" rx="6.5" fill={active ? "currentColor" : "none"} />
      <path d="M7 14h5M9.5 11.5v5" stroke={active ? "#fff" : "currentColor"} />
      <circle cx="17.6" cy="14" r="1.3" fill={active ? "#fff" : "currentColor"} stroke="none" />
      <circle cx="21" cy="14" r="1.3" fill={active ? "#fff" : "currentColor"} stroke="none" />
    </Tab>
  );
}
