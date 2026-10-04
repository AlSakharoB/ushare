import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './style.css';

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><main><h1>ReceiptSplit</h1><p>Разделите общий чек с друзьями.</p><p>Откройте приложение через Telegram.</p></main></QueryClientProvider></React.StrictMode>);
