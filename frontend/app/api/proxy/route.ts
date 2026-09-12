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
    const res = await fetch(`${DJANGO_BASE_URL}/api/v1/token/refresh/`, {
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

/**
 * Safely turn a Django response into a JSON-serializable body.
 * Django can return non-JSON (HTML error pages on 404/500, empty body on 204) —
 * never assume res.json() will succeed.
 */
async function safeReadBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null;

  const text = await res.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    // Upstream returned non-JSON (e.g. an HTML 404/500 page). Surface a
    // structured error instead of crashing on JSON.parse.
    return {
      error: 'Upstream returned a non-JSON response',
      status: res.status,
      preview: text.slice(0, 500),
    };
  }
}

async function forward(
  request: NextRequest,
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
): Promise<NextResponse> {
  const session = getSessionData(request);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const djangoPath = request.nextUrl.searchParams.get('path') || '';
  if (!djangoPath) {
    return NextResponse.json({ error: 'Missing path parameter' }, { status: 400 });
  }

  const hasBody = method === 'POST' || method === 'PATCH' || method === 'PUT';
  let body: string | undefined;
  if (hasBody) {
    const raw = await request.text();
    body = raw || undefined;
  }

  async function callDjango(accessToken: string) {
    return fetch(`${DJANGO_BASE_URL}${djangoPath}`, {
      method,
      headers: {
        ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
        Authorization: `Bearer ${accessToken}`,
      },
      ...(hasBody ? { body } : {}),
    });
  }

  try {
    let res = await callDjango(session.accessToken);
    let refreshedToken: string | null = null;

    if (res.status === 401) {
      refreshedToken = await refreshAccessToken(session.refreshToken);
      if (!refreshedToken) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
      }
      res = await callDjango(refreshedToken);
    }

    const responseBody = await safeReadBody(res);
    const response = NextResponse.json(responseBody, { status: res.status });

    if (refreshedToken) {
      response.cookies.set(
        'school-saas-session',
        JSON.stringify({ ...session, accessToken: refreshedToken }),
        {
          httpOnly: true,
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'lax',
        }
      );
    }

    return response;
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  return forward(request, 'GET');
}

export async function POST(request: NextRequest) {
  return forward(request, 'POST');
}

export async function PATCH(request: NextRequest) {
  return forward(request, 'PATCH');
}

export async function PUT(request: NextRequest) {
  return forward(request, 'PUT');
}

export async function DELETE(request: NextRequest) {
  return forward(request, 'DELETE');
}
