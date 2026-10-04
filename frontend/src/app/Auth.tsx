import { useEffect, useState } from 'react';
import { api, setCsrfToken } from '../shared/api';
import { telegramApp } from './telegram';
import type { components } from '../shared/api.generated';

type User = components['schemas']['UserDTO'];
export function Auth({ children }: { children: (user: User) => React.ReactNode }) {
  const [user, setUser] = useState<User>();
  const [error, setError] = useState('');
  useEffect(() => {
    const tg = telegramApp(); tg?.ready(); tg?.expand();
    if (!tg?.initData) { setError('Откройте приложение через Telegram'); return; }
    let active = true;
    api<{ user: User; csrf_token: string }>('/auth/telegram', 'POST', { init_data: tg.initData }).then(result => {
      if (active) { setCsrfToken(result.csrf_token); setUser(result.user); }
    }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  if (error) return <section role="alert"><h2>Вход в ReceiptSplit</h2><p>{error}</p><button onClick={() => window.location.reload()}>Повторить</button></section>;
  if (!user) return <p role="status">Проверяем вход…</p>;
  return children(user);
}
