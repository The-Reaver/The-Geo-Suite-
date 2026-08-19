"use client";

/*
 * 2026-08-09 GEO Brain Trust Presentation Mode review, Jasiah (QA) finding:
 * no global error boundary exists anywhere in frontend/app, so a render
 * error inside the Nova shell would surface as a blank white screen with no
 * recovery path — the worst possible failure mode in front of a prospect.
 *
 * This wraps NovaShell only, not the whole app: a crash here should not be
 * conflated with the app-wide error handling other routes may already have,
 * and keeping the blast radius scoped to /nova matches the "styles stay
 * scoped under .nova-app" discipline already established in this file's
 * sibling components.
 *
 * Deliberately a plain class component (React does not offer a hook API for
 * componentDidCatch as of this writing), and deliberately minimal: it does
 * not attempt to report the error anywhere, since no error-reporting service
 * is wired into this project yet. That is a separate, undecided piece of
 * infrastructure, not something to bolt on silently here.
 */

import { Component, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export default class NovaErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // eslint-disable-next-line no-console
    console.error("Nova shell crashed:", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="nv-crash">
          <h2>Something went wrong in the demo.</h2>
          <p>
            This screen hit an unexpected error. Nothing was lost on the backend —
            reload to start the demo over.
          </p>
          <button type="button" onClick={() => window.location.reload()}>
            Reload demo
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
