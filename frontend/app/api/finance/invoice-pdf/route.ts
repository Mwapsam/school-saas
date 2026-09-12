/**
 * Dedicated PDF-download route for a guardian's consolidated FamilyInvoice.
 *
 * The shared BFF proxy (`/api/proxy`) always returns `NextResponse.json(...)`,
 * so it cannot pass through a binary `application/pdf` response from Django
 * without corrupting it. This route follows the same session/token pattern
 * as the proxy but streams the Django response body and headers straight
 * through (see `student-ledger-export/route.ts` for the CSV equivalent),
 * which lets a plain `<a href>` navigation render/download the PDF.
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

  const invoiceId = request.nextUrl.searchParams.get('id');
  if (!invoiceId) {
    return NextResponse.json({ error: 'Missing invoice id' }, { status: 400 });
  }

  const targetPath = `/api/v1/invoices/${invoiceId}/pdf/`;

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
        { error: 'Failed to generate invoice PDF', status: res.status, preview: text.slice(0, 500) },
        { status: res.status }
      );
    }

    const pdfBytes = await res.arrayBuffer();
    const response = new NextResponse(pdfBytes, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': res.headers.get('Content-Disposition') || 'inline; filename="invoice.pdf"',
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
    console.error('Invoice PDF export error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
