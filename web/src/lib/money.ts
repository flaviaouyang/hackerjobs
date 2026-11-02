import type { Pay, Rates } from './types';

const SYMBOLS: Record<string, string> = { USD: '$', CAD: 'CA$', AUD: 'A$', EUR: '€', GBP: '£', INR: '₹', JPY: '¥' };
const PERIOD_LABELS: Record<string, string> = { year: 'per year', month: 'per month', day: 'per day', hour: 'per hour' };

/** Convert an amount between currencies through the Bank of Canada's CAD rates; null if either is unknown. */
export function convert(amount: number, from: string | null, to: string, rates: Rates): number | null {
  const source = from ? rates.cad_per_unit[from] : undefined;
  const target = rates.cad_per_unit[to];
  if (source === undefined || target === undefined) return null;
  return (amount * source) / target;
}

/** "175k" for thousands, "1.2M" for millions, plain digits below 1,000 (hourly rates). */
function short(amount: number): string {
  if (amount >= 1_000_000) return `${+(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `${Math.round(amount / 1_000)}k`;
  return `${+amount.toFixed(2)}`;
}

function symbol(currency: string): string {
  return SYMBOLS[currency] ?? `${currency} `;
}

/** "$175k–225k", or "$180k" when the range is a single figure. */
export function formatRange(min: number, max: number, currency: string): string {
  const low = short(min);
  const high = short(max);
  return `${symbol(currency)}${low === high ? low : `${low}–${high}`}`;
}

export interface DisplayPay {
  /** The range in the visitor's currency, or in its own currency when it can't be converted. */
  main: string;
  /** The original range when it was converted, e.g. "£100k–120k". */
  original: string | null;
  period: string;
}

/** Describe a pay range for display, converted to the visitor's currency when possible. */
export function displayPay(pay: Pay, currency: string, rates: Rates): DisplayPay {
  const own = pay.currency ?? 'USD';
  const period = PERIOD_LABELS[pay.period ?? 'year'];
  const min = convert(pay.min, own, currency, rates);
  const max = convert(pay.max, own, currency, rates);
  if (own === currency || min === null || max === null) {
    return { main: formatRange(pay.min, pay.max, own), original: null, period };
  }
  return { main: formatRange(min, max, currency), original: formatRange(pay.min, pay.max, own), period };
}

/** The top of a yearly range in the visitor's currency; null for other periods or unknown currencies. */
export function yearlyMax(pay: Pay | null, currency: string, rates: Rates): number | null {
  if (!pay || (pay.period ?? 'year') !== 'year') return null;
  return convert(pay.max, pay.currency ?? 'USD', currency, rates);
}
