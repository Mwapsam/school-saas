/**
 * Session management for BFF architecture.
 *
 * The browser never directly holds Django JWT tokens.
 * Next.js route handlers exchange Django tokens for httpOnly session cookies.
 * This prevents XSS token theft and centralizes auth logic.
 */

import { cookies } from 'next/headers';

const SESSION_COOKIE_NAME = 'school-saas-session';
const DJANGO_ACCESS_TOKEN_KEY = 'django-access-token';
const DJANGO_REFRESH_TOKEN_KEY = 'django-refresh-token';

export interface SessionData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

/**
 * Store session data (tokens) server-side in httpOnly cookie.
 * Only accessible to Next.js server; never sent to browser JS.
 */
export async function setSession(data: SessionData): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, JSON.stringify(data), {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: data.expiresAt - Date.now(),
  });
}

/**
 * Retrieve session data (tokens) from httpOnly cookie.
 */
export async function getSession(): Promise<SessionData | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME);

  if (!sessionCookie?.value) {
    return null;
  }

  try {
    return JSON.parse(sessionCookie.value);
  } catch {
    return null;
  }
}

/**
 * Clear session (logout).
 */
export async function clearSession(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}

/**
 * Check if session is expired.
 */
export async function isSessionExpired(): Promise<boolean> {
  const session = await getSession();
  if (!session) return true;
  return Date.now() > session.expiresAt;
}
