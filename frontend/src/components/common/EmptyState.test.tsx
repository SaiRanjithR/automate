import { render, screen } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { EmptyState } from '@/components/common/EmptyState'

describe('EmptyState', () => {
  it('renders title, description and the next action', () => {
    render(
      <EmptyState
        icon={FileText}
        title="Upload your first tender"
        description="Add an RFP to begin."
        action={<button type="button">Start</button>}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Upload your first tender' })).toBeInTheDocument()
    expect(screen.getByText('Add an RFP to begin.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument()
  })
})
