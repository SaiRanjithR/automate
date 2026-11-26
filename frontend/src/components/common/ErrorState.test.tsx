import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ErrorState } from '@/components/common/ErrorState'

describe('ErrorState', () => {
  it('shows the message as an alert and calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<ErrorState message="Could not load projects" onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Could not load projects')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('hides Retry when no handler is given', () => {
    render(<ErrorState message="Failed" />)
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })
})
