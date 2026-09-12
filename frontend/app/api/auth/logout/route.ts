/**
 * BFF route handler for logout.
 *
 * Clears the httpOnly session cookie. Django tokens simply expire server-side;
 * no need to call Django since the browser never held them.
 */

import { NextResponse } from 'next/server';

export async function POST() {
  const response = NextResponse.json({ success: true }, { status: 200 });
  response.cookies.delete('school-saas-session');
  return response;
}
