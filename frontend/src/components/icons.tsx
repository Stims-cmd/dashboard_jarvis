// Inline SVG icons: nothing is loaded from outside. They follow the text colour (currentColor).
import type { ReactNode, SVGProps } from 'react'

function Icon({ children, ...props }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg
      width="1em"
      height="1em"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  )
}

export const MinimizeIcon = () => (
  <Icon>
    <path d="M6 18h12" />
  </Icon>
)

export const MaximizeIcon = () => (
  <Icon>
    <rect x="5" y="5" width="14" height="14" rx="1.5" />
  </Icon>
)

export const RestoreIcon = () => (
  <Icon>
    <rect x="5" y="9" width="10" height="10" rx="1.5" />
    <path d="M9 9V6.5A1.5 1.5 0 0 1 10.5 5h7A1.5 1.5 0 0 1 19 6.5v7a1.5 1.5 0 0 1-1.5 1.5H15" />
  </Icon>
)

export const ShieldIcon = () => (
  <Icon>
    <path d="M12 3 5 6v5c0 4.4 3 8.3 7 10 4-1.7 7-5.6 7-10V6l-7-3Z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
)

export const EuroIcon = () => (
  <Icon>
    <path d="M17 6.5A7 7 0 1 0 17 17.5" />
    <path d="M4 10h9M4 14h9" />
  </Icon>
)

export const RadarIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <path d="M12 12 18.5 5.5" />
    <circle cx="12" cy="12" r="1" fill="currentColor" />
  </Icon>
)

export const TagIcon = () => (
  <Icon>
    <path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9-9-9Z" />
    <circle cx="7.5" cy="7.5" r="1.5" />
  </Icon>
)

export const WindowIcon = () => (
  <Icon>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 9h18" />
  </Icon>
)

export const GridIcon = () => (
  <Icon>
    <rect x="4" y="4" width="7" height="7" rx="1" />
    <rect x="13" y="4" width="7" height="7" rx="1" />
    <rect x="4" y="13" width="7" height="7" rx="1" />
    <rect x="13" y="13" width="7" height="7" rx="1" />
  </Icon>
)

export const SunIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icon>
)

export const MoonIcon = () => (
  <Icon>
    <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />
  </Icon>
)

export const PowerIcon = () => (
  <Icon>
    <path d="M12 3v8" />
    <path d="M6.3 6.8a8 8 0 1 0 11.4 0" />
  </Icon>
)

/** Arc-reactor style logo of Jarvis. */
export function ReactorLogo({ size = 28, spinning = false }: { size?: number; spinning?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false" className="reactor">
      <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.5" />
      <g className={spinning ? 'reactor-spin' : undefined}>
        <circle
          cx="24"
          cy="24"
          r="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeDasharray="7 4.6"
          strokeLinecap="round"
        />
      </g>
      <circle cx="24" cy="24" r="9" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="24" cy="24" r="4.5" fill="currentColor" className="reactor-core" />
    </svg>
  )
}