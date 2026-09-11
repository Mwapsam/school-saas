/**
 * BFF proxy route for all authenticated Django API calls.
 *
 * All client-side API calls route through this proxy:
 * Browser → /api/proxy → Django
 *
 * This route:
 * 1. Reads Django access token from httpOnly session cookie
 * 2. Includes token in Authorization header to Django
 * 3. If token expired (401), refreshes and retries
 * 4. Returns Django response to client
 *
 * Browser never sees tokens; token refresh happens server-side.
 */

import { NextRequest, NextResponse } from 'next/server';

const DJANGO_BASE_URL = process.env.NEXT_PUBLIC_DJANGO_BASE_URL || 'http://localhost:8000';

interface SessionData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

function getSessionData(request: NextRequest): SessionData | null {
  const sessionCookie = request.cookies.get('school-saas-session');
  if (!sessionCookie?.value) return null;

  try {
    return JSON.parse(sessionCookie.value);
  } catch {
    return null;
  }
}

async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  try {
    const res = await fetch(`${DJANGO_BASE_URL}/api/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!res.ok) return null;

    const { access } = await res.json();
    return access;
  } catch {
    return null;
  }
}

export async function GET(request: NextRequest) {
  const session = getSessionData(request);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const djangoPath = request.nextUrl.searchParams.get('path') || '';
  if (!djangoPath) {
    return NextResponse.json({ error: 'Missing path parameter' }, { status: 400 });
  }

  try {
    const res = await fetch(`${DJANGO_BASE_URL}${djangoPath}`, {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    // If 401, try refreshing token and retry
    if (res.status === 401) {
      const newAccessToken = await refreshAccessToken(session.refreshToken);
      if (!newAccessToken) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
      }

      const retryRes = await fetch(`${DJANGO_BASE_URL}${djangoPath}`, {
        headers: {
          Authorization: `Bearer ${newAccessToken}`,
        },
      });

      // Update session cookie with new token
      const response = NextResponse.json(await retryRes.json(), {
        status: retryRes.status,
      });
      response.cookies.set('school-saas-session', JSON.stringify({
        ...session,
        accessToken: newAccessToken,
      }), {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
      });

      return response;
    }

    return NextResponse.json(await res.json(), { status: res.status });
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const session = getSessionData(request);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const djangoPath = request.nextUrl.searchParams.get('path') || '';
  if (!djangoPath) {
    return NextResponse.json({ error: 'Missing path parameter' }, { status: 400 });
  }

  const body = await request.json();

  try {
    const res = await fetch(`${DJANGO_BASE_URL}${djangoPath}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.accessToken}`,
      },
      body: JSON.stringify(body),
    });

    // Handle 401 and refresh if needed
    if (res.status === 401) {
      const newAccessToken = await refreshAccessToken(session.refreshToken);
      if (!newAccessToken) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
      }

      const retryRes = await fetch(`${DJANGO_BASE_URL}${djangoPath}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${newAccessToken}`,
        },
        body: JSON.stringify(body),
      });

      const response = NextResponse.json(await retryRes.json(), {
        status: retryRes.status,
      });
      response.cookies.set('school-saas-session', JSON.stringify({
        ...session,
        accessToken: newAccessToken,
      }), {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
      });

      return response;
    }

    return NextResponse.json(await res.json(), { status: res.status });
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
