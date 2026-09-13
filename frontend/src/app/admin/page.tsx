"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { StatsSection } from "./components/stats-section";
import { RecentSchools } from "./components/recent-schools";

export default function AdminDashboard() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-2 text-slate-600">
          Manage schools, view statistics, and handle demo requests
        </p>
      </div>

      {/* Stats Section */}
      <StatsSection />

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-lg font-semibold text-slate-900">
            Provision New School
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Create a new tenant and configure its initial settings.
          </p>
          <Link href="/admin/tenants/new">
            <Button className="mt-4">Create School</Button>
          </Link>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold text-slate-900">
            Manage Existing Schools
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            View, edit, and manage all provisioned schools.
          </p>
          <Link href="/admin/tenants">
            <Button className="mt-4" variant="outline">
              View Schools
            </Button>
          </Link>
        </Card>
      </div>

      {/* Recent Schools */}
      <RecentSchools />
    </div>
  );
}
