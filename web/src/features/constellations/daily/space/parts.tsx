import type { ReactNode } from "react";
import { ChevronLeft } from "lucide-react";

/** Three stars joined by two lines: the Space mark. */
export function Glyph({ size = 20, color = "#fff" }: { size?: number; color?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke={color} strokeWidth="1.6" aria-hidden="true">
      <path d="M5 17 L10 7 L19 12" />
      <circle cx="5" cy="17" r="2" fill={color} />
      <circle cx="10" cy="7" r="2" fill={color} />
      <circle cx="19" cy="12" r="2" fill={color} />
    </svg>
  );
}

export function SpaceAvatar({ size = 40 }: { size?: number }) {
  return (
    <span className="spc-avatar" style={{ width: size, height: size }}>
      <Glyph size={size / 2} />
    </span>
  );
}

export function Toggle({ on, label, onChange, disabled, testId }: { on: boolean; label: string; onChange: () => void; disabled?: boolean; testId?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      className={`spc-switch${on ? " is-on" : ""}`}
      onClick={onChange}
      disabled={disabled}
      data-testid={testId}
    >
      <span />
    </button>
  );
}

export function TopBar({ title, onBack, dark, children, dot }: { title: ReactNode; onBack?: () => void; dark?: boolean; children?: ReactNode; dot?: string }) {
  return (
    <div className={`spc-topbar${dark ? " is-dark" : ""}`}>
      {onBack && (
        <button type="button" className="spc-round" onClick={onBack} aria-label="Back">
          <ChevronLeft size={22} />
        </button>
      )}
      {dot && <span className="spc-dot" style={{ background: dot }} aria-hidden="true" />}
      <h2 className="spc-topbar-title">{title}</h2>
      {children}
    </div>
  );
}

/** Marks content that is not from a producer yet (contract 3.0.0 pending). */
export function PreviewTag({ children = "Preview · synthetic", dark }: { children?: ReactNode; dark?: boolean }) {
  return <span className={`spc-preview${dark ? " is-dark" : ""}`}>{children}</span>;
}

export function StarField({ dense }: { dense?: boolean }) {
  return <div className={`spc-starfield${dense ? " is-dense" : ""}`} aria-hidden="true" />;
}

export function Waveform() {
  return (
    <span className="spc-wave" aria-hidden="true">
      {[14, 32, 22, 38, 18, 28, 12].map((h, i) => (
        <i key={i} style={{ height: h, animationDelay: `${i * 90}ms` }} />
      ))}
    </span>
  );
}

export function MicIcon({ color = "currentColor" }: { color?: string }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}
