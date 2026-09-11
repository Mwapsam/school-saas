/**
 * Next.js middleware for tenant resolution and auth protection.
 *
 * Tenant is derived from subdomain (e.g., school-a.yourplatform.com → school-a).
 * Tenancy is never accepted from client-supplied data (query params, headers, etc.).
 * Django's django-tenants middleware validates the Host header and sets the actual tenant.
 *
 * This middleware:
 * 1. Extracts subdomain from Host header
 * 2. Redirects to login if not authenticated
 * 3. Allows /auth/* routes (login, signup, etc.) without auth
 * 4. Protects all /dashboard/* routes with auth check
 */

import { NextRequest, NextResponse } from 'next/server';
import Cookies from 'js-cookie';

const PUBLIC_ROUTES = ['/auth/login', '/auth/signup', '/auth/forgot-password', '/auth/reset', '/health'];
const PROTECTED_ROUTES = ['/dashboard'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Extract subdomain from Host header
  const host = request.headers.get('host') || '';
  const subdomain = extractSubdomain(host);

  // Store subdomain in response headers (accessible to route handlers)
  const response = NextResponse.next();
  response.headers.set('X-Subdomain', subdomain);

  // Public routes (no auth required)
  if (PUBLIC_ROUTES.some((route) => pathname.startsWith(route))) {
    return response;
  }

  // Protected routes (require auth)
  if (PROTECTED_ROUTES.some((route) => pathname.startsWith(route))) {
    const sessionCookie = request.cookies.get('school-saas-session');
    if (!sessionCookie) {
      // Redirect to login, preserving the intended destination
      const loginUrl = new URL('/auth/login', request.url);
      loginUrl.searchParams.set('from', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return response;
}

/**
 * Extract subdomain from host.
 * Examples:
 * - school-a.yourplatform.com → school-a
 * - localhost:3000 → localhost
 * - 127.0.0.1:3000 → 127.0.0.1
 * - lvh.me → lvh.me (wildcard subdomain testing)
 */
function extractSubdomain(host: string): string {
  const hostname = host.split(':')[0]; // Remove port
  const parts = hostname.split('.');

  // Single-part hostname (localhost, IP)
  if (parts.length === 1) {
    return parts[0];
  }

  // Multi-part hostname — first part is subdomain
  return parts[0];
}

export const config = {
  matcher: ['/((?!_next|static|favicon.ico|health).*)'],
};
