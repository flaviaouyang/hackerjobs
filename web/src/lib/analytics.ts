// GoatCounter, loaded by Base.astro only when PUBLIC_GOATCOUNTER_CODE is set at build time.

declare global {
  interface Window {
    goatcounter?: {
      path?: (path: string) => string | null;
      count?: (vars: { path: string; title?: string; event?: boolean }) => void;
    };
  }
}

/** Kinds of link clicks that are counted: totals only, nothing about the post or company. */
export type CountedClick = 'apply' | 'email-candidate' | 'hn-post';

/** Count a click as a GoatCounter event; does nothing when analytics is off. */
export function countClick(name: CountedClick): void {
  window.goatcounter?.count?.({ path: name, event: true });
}
