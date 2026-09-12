/**
 * Dedicated CSV-export route for the Particular-wise Student Transaction
 * Report (student ledger).
 *
 * The shared BFF proxy (`/api/proxy`) always returns `NextResponse.json(...)`,
 * so it cannot pass through a `text/csv` response from Django without
 * corrupting it. This route follows the same session/token pattern as the
 * proxy but streams the Django response body and headers straight through,
 * which lets a plain `<a href>` / `window.location` navigation trigger a
 * real browser file download.
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

export async function GET(request: NextRequest) {
  const session = getSessionData(request);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const search = request.nextUrl.search;
  const targetPath = `/api/v1/finance/student-ledger/${search ? `${search}&format=csv` : '?format=csv'}`;

  async function callDjango(accessToken: string) {
    return fetch(`${DJANGO_BASE_URL}${targetPath}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
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

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json(
        { error: 'Failed to generate report', status: res.status, preview: text.slice(0, 500) },
        { status: res.status }
      );
    }

    const csvText = await res.text();
    const response = new NextResponse(csvText, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition':
          res.headers.get('Content-Disposition') ||
          'attachment; filename="particular_wise_student_transaction_report.csv"',
      },
    });

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
    console.error('Student ledger CSV export error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
