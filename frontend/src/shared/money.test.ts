import { expect, test } from 'vitest';
import { formatMoney } from './money';
test('formats minor units and rejects unsafe numbers', () => {
  expect(formatMoney(12345).replaceAll(/\s/g, ' ')).toBe('123,45 ₽');
  expect(() => formatMoney(0.1)).toThrow();
});
