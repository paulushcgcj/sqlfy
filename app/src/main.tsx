import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from '@tanstack/react-router';

import './index.scss';
import { AppContextProvider } from './context/AppContext';
import { SAMPLE_MIGRATIONS } from './data/samples';
import { router } from './router';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppContextProvider initialFiles={SAMPLE_MIGRATIONS}>
      <RouterProvider router={router} />
    </AppContextProvider>
  </StrictMode>,
);
