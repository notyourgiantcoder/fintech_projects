/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
  /** "1" turns sign-in off for local development. Never set it on a deployment. */
  readonly VITE_DEV_AUTH?: string
  /** Entra app registration for OneDrive/SharePoint sync (optional). */
  readonly VITE_MS_CLIENT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
