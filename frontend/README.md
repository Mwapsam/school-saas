# School Management Platform — Next.js Frontend

## Architecture Overview

### BFF (Backend-for-Frontend) Pattern

All API calls flow through Next.js route handlers, **never directly from the browser to Django**:

```
Browser (Next.js client) → Next.js Route Handlers (server) → Django API (server)
```

**Benefits:**
- JWT tokens stored in httpOnly cookies (never in client JS — prevents XSS theft)
- Token refresh handled transparently server-side
- Single auth boundary (centralized auth logic)
- Future mobile clients can call Django directly with own auth flow (API unchanged)

### Tenant Resolution

Tenancy is derived from the **subdomain**, validated by Django's `django-tenants`:

```
school-a.yourplatform.com → Next.js middleware extracts "school-a"
                         → Django's Host header validates tenant
                         → Tenant-specific schema queried
```

**Important:** Tenancy is never accepted from client-supplied data (query params, body, headers). Django is the sole authority.

### Bootstrap Endpoint

On first load, the frontend calls `/api/v1/bootstrap/` to fetch:
- **Tenant branding**: logo, colors, name, address, etc.
- **User info**: username, email, role
- **Capabilities**: permission strings for UI gating (e.g., `students.view`, `finance.invoices.create`)
- **Terminology**: per-tenant noun overrides (e.g., `student: "Pupil"`, `course: "Subject"`)
- **Modules**: enabled/disabled product areas (e.g., `finance: true`, `library: false`)

This data populates the Zustand tenant store, used throughout the app for:
- Conditional rendering (show "Students" nav only if module enabled)
- Permission checks (hide "Create Invoice" button if user lacks `finance.invoices.create`)
- Theming (MUI theme generated from bootstrap colors)

**Note:** Backend always enforces every permission — frontend checks are UX only.

---

## Project Structure

```
frontend/
├── app/                          Next.js App Router
│   ├── layout.tsx                Root layout (providers, theming)
│   ├── auth/
│   │   └── login/page.tsx         Login form
│   ├── dashboard/
│   │   └── page.tsx              Dashboard home
│   ├── api/
│   │   ├── auth/login/route.ts   BFF login (exchanges credentials for tokens)
│   │   └── proxy/route.ts        BFF proxy (all authenticated API calls)
│   └── ...                       More domain routes (students/, finance/, etc.)
│
├── lib/
│   ├── api/
│   │   └── client.ts             Typed API client (uses /api/proxy behind the scenes)
│   ├── auth/
│   │   └── session.ts            Session cookie management (server-side)
│   ├── tenant/
│   │   ├── bootstrap.ts          Bootstrap data fetching
│   │   └── store.ts              Zustand store (global tenant state)
│   └── ...
│
├── components/
│   ├── ui/                       Design system primitives (MUI wrappers)
│   ├── layout/                   Layout components (AppBar, Sidebar, etc.)
│   ├── data-table/               Table components with sorting/filtering
│   └── ...
│
├── features/
│   ├── students/                 Student domain-specific logic/hooks
│   ├── finance/                  Finance domain-specific logic/hooks
│   ├── hr/                       HR domain-specific logic/hooks
│   └── ...
│
├── middleware.ts                 Tenant resolution + auth protection
├── next.config.js                Next.js configuration
├── tsconfig.json                 TypeScript configuration
└── package.json                  Dependencies
```

---

## Setup

### Prerequisites
- Node.js 18+
- Django backend running at `http://localhost:8000` (or set `NEXT_PUBLIC_DJANGO_BASE_URL`)

### Install Dependencies
```bash
cd frontend
npm install
```

### Environment Variables
Create `.env.local`:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_DJANGO_BASE_URL=http://localhost:8000
```

### Run Dev Server
```bash
npm run dev
```

Visit `http://localhost:3000/auth/login` (or a subdomain like `http://school-a.localhost:3000/`)

---

## Key Flows

### Login Flow

1. **User enters credentials** in login form
2. **Browser POSTs** to `/api/auth/login` (Next.js route handler)
3. **Route handler POSTs** credentials to Django's `/api/token/` endpoint
4. **Django returns** access + refresh tokens
5. **Route handler stores** tokens in httpOnly `school-saas-session` cookie
6. **Browser never sees tokens** (httpOnly prevents JS access)
7. **Redirect to dashboard**

### Authenticated API Call Flow

1. **Client component** calls `apiClient.get('/students/')`
2. **API client** POSTs to `/api/proxy?path=/api/v1/students/`
3. **Route handler** reads httpOnly session cookie → extracts Django access token
4. **Route handler** calls Django with `Authorization: Bearer <token>`
5. **Django validates token** + tenant isolation
6. **Django returns** 200 OK or 401 Unauthorized
7. **If 401**, route handler refreshes token server-side + retries transparently
8. **Response returned to client** (client never knows about token refresh)

### Bootstrap Flow

1. **Dashboard page** loads
2. **useEffect** calls `fetchBootstrap()`
3. **API client** POSTs to `/api/proxy?path=/api/v1/bootstrap/`
4. **Route handler** includes access token, calls Django
5. **Django returns** tenant config + user info + capabilities + modules + terminology
6. **Zustand store** updated with bootstrap data
7. **MUI theme** generated from bootstrap colors (optional, currently uses default)
8. **Navigation renders** only enabled modules
9. **Permission checks** use bootstrap capabilities for UI gating

---

## State Management

### Zustand Tenant Store

Global state for bootstrap data:

```typescript
import { useTenantStore } from '@/lib/tenant/store';

function MyComponent() {
  const { bootstrap, can, isModuleEnabled, getTerminology } = useTenantStore();

  // Check capability (for UI gating)
  if (!can('students.view')) return <div>No access</div>;

  // Check module enabled
  if (!isModuleEnabled('finance')) return <div>Finance disabled</div>;

  // Get terminology override
  const studentLabel = getTerminology('student', 'Student');

  return <div>{studentLabel}</div>;
}
```

---

## API Integration

### Typed API Client

```typescript
import { apiClient } from '@/lib/api/client';

// Automatic token handling + 401 refresh
const students = await apiClient.get('/students/');

const created = await apiClient.post('/students/', {
  admission_number: 'STU001',
  full_name: 'John Doe',
});

const updated = await apiClient.patch('/students/1/', {
  full_name: 'Jane Doe',
});

await apiClient.delete('/students/1/');
```

All requests:
- ✅ Include Django access token (from httpOnly cookie)
- ✅ Refresh token if expired (server-side, transparent to client)
- ✅ Handle 401/403 errors
- ✅ Include tenant identity (Django derives from Host header)

---

## Security Considerations

### Token Storage
- ✅ Access + refresh tokens stored in httpOnly cookie (not in localStorage)
- ✅ Cookie only sent to same-origin (Same-Site=Lax)
- ✅ Secure flag on HTTPS (production only)
- ✅ Browser JS cannot access tokens (prevents XSS theft)

### Tenant Isolation
- ✅ Tenant derived from subdomain (extracted in middleware)
- ✅ Django validates Host header + enforces schema isolation
- ✅ No client-supplied tenant IDs trusted
- ✅ Backend tests verify cross-tenant isolation

### Permission Checks
- ✅ Frontend checks capabilities for UX (hiding buttons, nav items)
- ✅ Backend enforces every permission (never trusts frontend)
- ✅ Disabled modules return 403 server-side
- ✅ Unauthenticated requests return 401

---

## Development Checklist

### Phase 1: Core Setup (Current)
- ✅ Scaffold Next.js app structure
- ✅ BFF auth (login route handler)
- ✅ BFF proxy (authenticated API calls)
- ✅ Tenant resolution middleware
- ✅ Bootstrap integration
- ✅ Zustand store
- ✅ Basic dashboard + login pages

### Phase 2: Domain Features (Next)
- [ ] Students feature (list, create, view, edit, delete)
- [ ] Finance feature (invoices, fees, transactions)
- [ ] HR feature (employees, leave, attendance)
- [ ] Admissions feature
- [ ] Hostel feature
- [ ] Transport feature
- [ ] Library feature

### Phase 3: Polish
- [ ] MUI theme generation from bootstrap colors
- [ ] Data table component (sorting, filtering, pagination)
- [ ] Form validation + error handling
- [ ] Loading states + skeletons
- [ ] Dark mode support
- [ ] Responsive design
- [ ] Accessibility (a11y)

### Phase 4: Deployment
- [ ] Docker build
- [ ] Environment configuration
- [ ] Performance optimization
- [ ] Analytics integration
- [ ] Error tracking (Sentry)

---

## Testing Locally with Subdomains

### Using `lvh.me` (requires DNS)
```bash
# *.lvh.me resolves to 127.0.0.1
npm run dev
# Visit: http://school-a.lvh.me:3000/auth/login
```

### Using Hosts File
Edit `/etc/hosts` (or `C:\Windows\System32\drivers\etc\hosts` on Windows):
```
127.0.0.1 localhost
127.0.0.1 school-a.localhost
127.0.0.1 school-b.localhost
```

Then:
```bash
npm run dev
# Visit: http://school-a.localhost:3000/auth/login
```

---

## Next Steps

1. **Implement Students feature** (first domain-specific feature)
   - Create `/app/dashboard/students/` pages (list, create, detail, edit)
   - Use React Query for data fetching/caching
   - Build data table component

2. **Build domain-specific features** (Finance, HR, Admissions, etc.)
   - Follow Students pattern
   - Reuse components from `components/` and `lib/`

3. **Integrate MUI theming** from bootstrap colors

4. **Add navigation** (sidebar/drawer with module-driven menu)

5. **Deploy** (Docker, etc.)

---

## Troubleshooting

### "Unauthorized" on bootstrap call
- Check Django backend is running (`http://localhost:8000`)
- Verify login succeeded (check `/api/auth/login` response)
- Confirm `school-saas-session` cookie exists (inspect with DevTools)

### Subdomain not resolving
- Check middleware.ts extracts subdomain correctly
- Verify Django's Host header matches expectation
- Test with `localhost` first (no subdomain)

### Token refresh not working
- Check `/api/proxy` route handler logs
- Verify refresh token in session cookie is valid
- Confirm Django's `/api/token/refresh/` endpoint works

---

## References

- [Next.js App Router](https://nextjs.org/docs/app)
- [MUI Documentation](https://mui.com)
- [React Query](https://tanstack.com/query)
- [Zustand](https://github.com/pmndrs/zustand)
- [BFF Architecture](https://www.patterns.dev/posts/backend-for-frontend)
- [Django Tenants](https://django-tenants.readthedocs.io)
