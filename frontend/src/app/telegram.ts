export interface TelegramApp {
  initData: string;
  initDataUnsafe?: { start_param?: string };
  ready(): void; expand(): void;
  viewportStableHeight?: number;
  colorScheme?: string;
  onEvent?: (event: string, listener: () => void) => void;
  offEvent?: (event: string, listener: () => void) => void;
  BackButton?: { show(): void; hide(): void; onClick(fn: () => void): void; offClick(fn: () => void): void };
}
declare global { interface Window { Telegram?: { WebApp?: TelegramApp } } }
export function telegramApp() { return window.Telegram?.WebApp; }
