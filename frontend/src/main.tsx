import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './style.css';
import { Auth } from './app/Auth';

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><main><h1>ReceiptSplit</h1><Auth>{user => <><p>{user.display_name}, разделите общий чек с друзьями.</p><p>Ваш Telegram подтверждён.</p></>}</Auth></main></QueryClientProvider></React.StrictMode>);
