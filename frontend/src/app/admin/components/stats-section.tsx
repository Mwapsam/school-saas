"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Building2, Users, FileText, TrendingUp } from "lucide-react";

interface Stat {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  description: string;
}

export function StatsSection() {
  const [stats, setStats] = React.useState<Stat[]>([
    {
      title: "Total Schools",
      value: "12",
      icon: <Building2 className="h-6 w-6 text-blue-600" />,
      description: "Active tenants",
    },
    {
      title: "Total Users",
      value: "1,242",
      icon: <Users className="h-6 w-6 text-green-600" />,
      description: "Across all schools",
    },
    {
      title: "Demo Requests",
      value: "8",
      icon: <FileText className="h-6 w-6 text-orange-600" />,
      description: "Pending",
    },
    {
      title: "System Health",
      value: "99.9%",
      icon: <TrendingUp className="h-6 w-6 text-emerald-600" />,
      description: "Uptime",
    },
  ]);

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat, idx) => (
        <Card key={idx} className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">{stat.title}</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">
                {stat.value}
              </p>
              <p className="mt-1 text-xs text-slate-500">{stat.description}</p>
            </div>
            <div className="rounded-lg bg-slate-100 p-3">{stat.icon}</div>
          </div>
        </Card>
      ))}
    </div>
  );
}
