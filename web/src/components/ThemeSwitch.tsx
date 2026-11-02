import { useEffect, useState } from 'preact/hooks';

type Theme = 'auto' | 'light' | 'dark';

// Base.astro applies a saved choice before the page paints; keep the key in step with it.
const KEY = 'theme';

const ICONS: Record<Theme, preact.JSX.Element> = {
  auto: <><rect x="3" y="4" width="18" height="12" /><path d="M8 20h8M12 16v4" /></>,
  light: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  dark: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />,
};
const LABELS: Record<Theme, string> = { auto: 'Match system', light: 'Light', dark: 'Dark' };

function saved(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === 'light' || value === 'dark' ? value : 'auto';
  } catch {
    return 'auto';
  }
}

/** Light, dark or the system's choice, remembered in this browser. */
export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>('auto');
  useEffect(() => setTheme(saved()), []);

  const choose = (next: Theme) => {
    setTheme(next);
    if (next === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
    try {
      if (next === 'auto') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      // Storage can be blocked; the choice still holds for this page view.
    }
  };

  return (
    <div class="field">
      <span class="label" id="theme-label">Theme</span>
      <div class="theme" role="group" aria-labelledby="theme-label">
        {(Object.keys(ICONS) as Theme[]).map((option) => (
          <button key={option} type="button" aria-pressed={theme === option} aria-label={LABELS[option]}
            title={LABELS[option]} onClick={() => choose(option)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
              {ICONS[option]}
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}
