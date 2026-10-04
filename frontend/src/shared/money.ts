export function formatMoney(minor: number): string {
  if (!Number.isSafeInteger(minor)) throw new Error('Некорректная сумма');
  return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }).format(minor / 100);
}
