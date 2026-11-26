import { Component, type ReactNode } from 'react'

type Props = { children: ReactNode; fallback: ReactNode }
type State = { failed: boolean }

/** Shows a static fallback when WebGL is unavailable or the 3D scene throws. */
export class SceneBoundary extends Component<Props, State> {
  override state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  override render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}
