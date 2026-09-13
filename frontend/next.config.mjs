/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,

  // Prevent Next.js from redirecting /api/foo/ → /api/foo (stripping trailing
  // slashes). Without this, the proxy forwards the slash-less URL to Django,
  // Django's APPEND_SLASH setting redirects back to the slash version with the
  // Host set to this origin, and the browser ends up in an infinite redirect loop
  // (ERR_TOO_MANY_REDIRECTS). All Django API endpoints expect trailing slashes.
  skipTrailingSlashRedirect: true,

  // Proxy all /api/* requests to the Django backend so the browser never
  // makes a cross-origin request. This eliminates CORS for browser traffic
  // entirely — no Access-Control-Allow-Origin header is required because
  // the request is same-origin from the browser's perspective.
  async rewrites() {
    const target = (
      process.env.NEXT_PUBLIC_API_BASE_URL || "https://portal2.pinewoodschoolzambia.com"
    ).replace(/\/$/, "");
    return [
      // Match with trailing slash first so the slash is preserved in the
      // destination. Without this rule, /:path* captures the path without the
      // trailing slash and the destination URL loses it, causing Django's
      // APPEND_SLASH middleware to 301-redirect every request.
      {
        source: "/api/:path*/",
        destination: `${target}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${target}/api/:path*`,
      },
    ];
  },

  // Tree-shake large packages — dramatically reduces JS bundle size
  experimental: {
    optimizePackageImports: [
      'lucide-react',
      '@radix-ui/react-avatar',
      '@radix-ui/react-dialog',
      '@radix-ui/react-dropdown-menu',
      '@radix-ui/react-label',
      '@radix-ui/react-select',
      '@radix-ui/react-separator',
      '@radix-ui/react-slot',
      '@radix-ui/react-tabs',
      'recharts',
    ],
  },

  // Strip console.* in production builds
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production'
      ? { exclude: ['error', 'warn'] }
      : false,
  },
};

export default nextConfig;
