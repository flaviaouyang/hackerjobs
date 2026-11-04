import { agoLabel } from '../lib/format';
import { CloseIcon, Out, REPO } from './shared';

// Base.astro hides a dismissed banner before the page paints; keep the key in step with it.
const KEY = 'banner';
const SCHEDULE = 'Updated at noon, 5 PM and 10 PM ET on the 1st-4th of each month, then at 9 AM ET on the 5th-10th and the 16th.';

function dismiss() {
  document.documentElement.dataset.banner = 'dismissed';
  try {
    localStorage.setItem(KEY, 'dismissed');
  } catch {
    // Storage can be blocked; the banner still stays hidden for this page view.
  }
}

/** When the board was last updated, how often it is, and where to report mistakes or help out. */
export function Banner({ updated }: { updated: string | null }) {
  return (
    <aside class="banner" aria-label="About the board">
      <div class="wrap">
        <p>
          {updated && (
            <>
              Updated <time dateTime={updated} title={SCHEDULE}>{agoLabel(updated)}</time>
              <span class="sep" aria-hidden="true">·</span>
            </>
          )}
          New posts arrive several times a day early in the month, then daily until the 10th.
          <span class="sep" aria-hidden="true">·</span>
          Spot a mistake? <Out href={`${REPO}/issues/new?template=wrong-details.yml`}>Report it</Out>
          <span class="sep" aria-hidden="true">·</span>
          <Out href={`${REPO}#contributing`}>Contributions welcome</Out>
        </p>
        <button type="button" class="close" aria-label="Dismiss" title="Dismiss" onClick={dismiss}>
          <CloseIcon />
        </button>
      </div>
    </aside>
  );
}
