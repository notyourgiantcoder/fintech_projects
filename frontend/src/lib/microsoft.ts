// Microsoft sign-in for OneDrive/SharePoint sync. The library is loaded only when someone
// connects, and the Graph token goes to our API per request; nothing stores it.
import type { PublicClientApplication } from '@azure/msal-browser'

export const MS_CLIENT_ID = import.meta.env.VITE_MS_CLIENT_ID as string | undefined
const SCOPES = ['Files.ReadWrite']

let app: Promise<PublicClientApplication> | null = null

function client(): Promise<PublicClientApplication> {
  if (!MS_CLIENT_ID) return Promise.reject(new Error('OneDrive sync isn’t configured.'))
  app ??= import('@azure/msal-browser').then(async ({ PublicClientApplication }) => {
    const pca = new PublicClientApplication({
      auth: {
        clientId: MS_CLIENT_ID,
        authority: 'https://login.microsoftonline.com/common',
        redirectUri: window.location.origin,
      },
      cache: { cacheLocation: 'sessionStorage' },
    })
    await pca.initialize()
    return pca
  })
  return app
}

/** A Graph access token, signing in with a popup the first time. */
export async function graphToken(): Promise<string> {
  const pca = await client()
  let account = pca.getAllAccounts()[0]
  if (!account) {
    const login = await pca.loginPopup({ scopes: SCOPES, prompt: 'select_account' })
    account = login.account
  }
  try {
    return (await pca.acquireTokenSilent({ scopes: SCOPES, account })).accessToken
  } catch {
    return (await pca.acquireTokenPopup({ scopes: SCOPES, account })).accessToken
  }
}
