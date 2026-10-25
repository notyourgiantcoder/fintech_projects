import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App.tsx'
import { AppAuthProvider } from './lib/auth'
import { CrewProvider } from './lib/crew'
import { ThemeProvider } from './lib/theme'
import './styles/tokens.css'
import './styles/base.css'
import './styles/app.css'
import './styles/chat.css'
import './styles/pages.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <AppAuthProvider>
          <CrewProvider>
            <App />
          </CrewProvider>
        </AppAuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
