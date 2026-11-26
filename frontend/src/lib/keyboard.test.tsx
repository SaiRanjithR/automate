import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useHotkeys } from '@/lib/keyboard'

function Harness({ onJ }: { onJ: () => void }) {
  useHotkeys({ j: onJ })
  return <input aria-label="field" />
}

describe('useHotkeys', () => {
  it('fires on key press outside fields and ignores typing', () => {
    const onJ = vi.fn()
    const { getByLabelText } = render(<Harness onJ={onJ} />)
    fireEvent.keyDown(window, { key: 'j' })
    expect(onJ).toHaveBeenCalledOnce()
    fireEvent.keyDown(getByLabelText('field'), { key: 'j' })
    expect(onJ).toHaveBeenCalledOnce()
  })
})
