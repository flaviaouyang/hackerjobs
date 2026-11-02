import { describe, expect, test } from 'bun:test';
import { pageWindow } from './pages';

describe('pagination', () => {
  test('shows the ends and two pages either side, with gaps', () => {
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(1, 10)).toEqual([1, 2, 3, null, 10]);
    expect(pageWindow(6, 12)).toEqual([1, null, 4, 5, 6, 7, 8, null, 12]);
    expect(pageWindow(10, 10)).toEqual([1, null, 8, 9, 10]);
  });
});
