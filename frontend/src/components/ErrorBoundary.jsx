import { Component } from 'react';

// Minimal error boundary — a WebGL / deck.gl / MapLibre failure (old GPU, blocked
// context) degrades to a message instead of white-screening the whole app. The data
// feed, brief, chat and exposure all keep working without the globe.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(err) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', err);
  }

  render() {
    if (this.state.failed) return this.props.fallback ?? null;
    return this.props.children;
  }
}
