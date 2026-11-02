/** Page numbers to show: the first, the last, and two either side of the current one. */
export function pageWindow(page: number, count: number): (number | null)[] {
  const shown = [...new Set([1, page - 2, page - 1, page, page + 1, page + 2, count])]
    .filter((number) => number >= 1 && number <= count)
    .sort((left, right) => left - right);
  return shown.flatMap((number, index) => (index && number - shown[index - 1] > 1 ? [null, number] : [number]));
}
