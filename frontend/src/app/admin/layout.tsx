"use client";

import React from "react";
import { useAuth } from "@/hooks/use-auth";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui/spinner";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, isSuperuser, user } = useAuth();
  const [isHydrated, setIsHydrated] = React.useState(false);

  React.useEffect(() => {
    setIsHydrated(true);
  }, []);

  if (!isHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!isAuthenticated || !isSuperuser) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50">
        <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
          <h1 className="text-2xl font-bold text-red-900">Access Denied</h1>
          <p className="mt-2 text-red-700">
            Only superusers can access the admin panel.
          </p>
          <Button
            onClick={() => router.push("/")}
            className="mt-4"
            variant="outline"
          >
            Go to Home
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-8">
          <h2 className="text-xl font-bold text-slate-900">Admin Panel</h2>
          <p className="text-sm text-slate-600">Tenant Management</p>
        </div>

        <nav className="space-y-2">
          <Link href="/admin" className="block">
            <Button
              variant="ghost"
              className="w-full justify-start"
            >
              Dashboard
            </Button>
          </Link>
          <Link href="/admin/tenants" className="block">
            <Button
              variant="ghost"
              className="w-full justify-start"
            >
              Manage Schools
            </Button>
          </Link>
          <Link href="/admin/tenants/new" className="block">
            <Button
              variant="ghost"
              className="w-full justify-start"
            >
              Provision New School
            </Button>
          </Link>
          <Link href="/admin/demo-requests" className="block">
            <Button
              variant="ghost"
              className="w-full justify-start"
            >
              Demo Requests
            </Button>
          </Link>
        </nav>

        <div className="mt-8 border-t border-slate-200 pt-6">
          <p className="text-xs text-slate-500">Logged in as:</p>
          <p className="font-medium text-slate-900">{user?.email}</p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8">
        {children}
      </main>
    </div>
  );
}
