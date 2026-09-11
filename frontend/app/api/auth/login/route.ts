/**
 * BFF route handler for login.
 *
 * Flow:
 * 1. Browser POSTs username/password to this route
 * 2. This route POSTs to Django's token endpoint
 * 3. Django returns access + refresh tokens
 * 4. This route stores tokens in httpOnly cookie (never sent to browser)
 * 5. Browser gets httpOnly session cookie
 * 6. Future requests include httpOnly cookie automatically
 * 7. Route handlers refresh tokens transparently
 *
 * Browser never sees JWT tokens.
 */

import { NextRequest, NextResponse } from 'next/server';

const DJANGO_BASE_URL = process.env.NEXT_PUBLIC_DJANGO_BASE_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { username, password } = body;

    if (!username || !password) {
      return NextResponse.json(
        { error: 'username and password required' },
        { status: 400 }
      );
    }

    // Exchange credentials for Django JWT tokens
    const tokenRes = await fetch(`${DJANGO_BASE_URL}/api/token/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!tokenRes.ok) {
      const data = await tokenRes.json();
      return NextResponse.json(
        { error: data.detail || 'Authentication failed' },
        { status: 401 }
      );
    }

    const { access, refresh } = await tokenRes.json();

    // Parse JWT to get expiration
    const accessPayload = JSON.parse(
      Buffer.from(access.split('.')[1], 'base64').toString()
    );
    const expiresAt = accessPayload.exp * 1000; // Convert to ms

    // Store tokens in httpOnly cookie
    const response = NextResponse.json(
      { success: true },
      { status: 200 }
    );

    const sessionData = JSON.stringify({
      accessToken: access,
      refreshToken: refresh,
      expiresAt,
    });

    response.cookies.set('school-saas-session', sessionData, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: expiresAt - Date.now(),
    });

    return response;
  } catch (error) {
    console.error('Login error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
