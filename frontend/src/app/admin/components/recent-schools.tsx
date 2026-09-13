"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface School {
  id: string;
  name: string;
  code: string;
  email: string;
  is_active: boolean;
  logo_url?: string;
}

export function RecentSchools() {
  const [schools, setSchools] = React.useState<School[]>([
    {
      id: "1",
      name: "Pinewood Preparatory School",
      code: "pinewood",
      email: "admin@pinewood.school",
      is_active: true,
    },
    {
      id: "2",
      name: "Nairobi High School",
      code: "nairobi_high",
      email: "info@nairobi-high.edu.ke",
      is_active: true,
    },
    {
      id: "3",
      name: "St. Mary's Academy",
      code: "st_marys",
      email: "contact@stmarys.ac.ke",
      is_active: false,
    },
  ]);

  return (
    <Card className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Recent Schools</h2>
        <Link href="/admin/tenants">
          <Button variant="outline" size="sm">
            View All
          </Button>
        </Link>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>School Name</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {schools.map((school) => (
              <TableRow key={school.id}>
                <TableCell className="font-medium">{school.name}</TableCell>
                <TableCell>{school.code}</TableCell>
                <TableCell>{school.email}</TableCell>
                <TableCell>
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      school.is_active
                        ? "bg-green-100 text-green-800"
                        : "bg-slate-100 text-slate-800"
                    }`}
                  >
                    {school.is_active ? "Active" : "Inactive"}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <Link href={`/admin/tenants/${school.id}`}>
                    <Button variant="ghost" size="sm">
                      Edit
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}
