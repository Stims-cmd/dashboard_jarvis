import type { ComponentType } from 'react'
import FinancesWindow from './FinancesWindow'
import LeboncoinWindow from './LeboncoinWindow'
import OsintWindow from './OsintWindow'
import VeilleCyberWindow from './VeilleCyberWindow'

// Maps a backend module id (GET /api/modules) to its window content.
export const windowComponents: Record<string, ComponentType> = {
  veille_cyber: VeilleCyberWindow,
  finances: FinancesWindow,
  osint: OsintWindow,
  leboncoin: LeboncoinWindow,
}
