import { describe, expect, test } from 'bun:test';
import { convert, displayPay, formatRange, yearlyMax } from './money';
import type { Rates } from './types';

const RATES: Rates = { date: '2026-10-30', cad_per_unit: { CAD: 1, USD: 1.396, GBP: 1.8699 } };

describe('money', () => {
  test('converts through CAD rates', () => {
    expect(convert(100, 'GBP', 'USD', RATES)).toBeCloseTo(133.95, 2);
    expect(convert(100, 'XYZ', 'USD', RATES)).toBeNull();
  });

  test('formats ranges compactly', () => {
    expect(formatRange(175_000, 225_000, 'USD')).toBe('$175k–225k');
    expect(formatRange(180_000, 180_000, 'GBP')).toBe('£180k');
    expect(formatRange(45, 70, 'PLN')).toBe('PLN 45–70');
    expect(formatRange(1_200_000, 1_500_000, 'INR')).toBe('₹1.2M–1.5M');
  });

  test('shows the original when converted', () => {
    const pay = { min: 100_000, max: 120_000, currency: 'GBP', period: 'year' as const };
    expect(displayPay(pay, 'USD', RATES)).toEqual({ main: '$134k–161k', original: '£100k–120k', period: 'per year' });
    expect(displayPay(pay, 'GBP', RATES)).toEqual({ main: '£100k–120k', original: null, period: 'per year' });
  });

  test('keeps pay in its own currency when it cannot be converted', () => {
    const pay = { min: 45, max: 70, currency: 'PLN', period: 'hour' as const };
    expect(displayPay(pay, 'USD', RATES)).toEqual({ main: 'PLN 45–70', original: null, period: 'per hour' });
  });

  test('only yearly pay counts toward the pay filter', () => {
    expect(yearlyMax({ min: 1, max: 2, currency: 'USD', period: 'hour' }, 'USD', RATES)).toBeNull();
    expect(yearlyMax({ min: 1, max: 100_000, currency: 'USD', period: 'year' }, 'USD', RATES)).toBe(100_000);
  });
});
