import type { ReactNode } from 'react'
import { EuroIcon, RadarIcon, ShieldIcon, TagIcon, WindowIcon } from './icons'

// Icon of each module window (backend module id -> icon).
const moduleIcons: Record<string, () => ReactNode> = {
  veille_cyber: ShieldIcon,
  finances: EuroIcon,
  osint: RadarIcon,
  leboncoin: TagIcon,
}

export const iconOf = (moduleId: string) => moduleIcons[moduleId] ?? WindowIcon
