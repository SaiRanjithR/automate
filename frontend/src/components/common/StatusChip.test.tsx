import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusChip, type ComplianceStatus } from '@/components/common/StatusChip'

describe('StatusChip', () => {
  it.each<[ComplianceStatus, string]>([
    ['fully_compliant', 'Full'],
    ['partially_compliant', 'Partial'],
    ['compliant_with_customisation', 'Custom'],
    ['non_compliant', 'Non-compliant'],
    ['gap', 'Gap'],
    ['draft', 'AI draft'],
  ])('shows a text label for %s', (status, label) => {
    render(<StatusChip status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
