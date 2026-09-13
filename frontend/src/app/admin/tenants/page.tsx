"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Search } from "lucide-react";

interface School {
  id: string;
  name: string;
  code: string;
  email: string;
  is_active: boolean;
}

export default function TenantsPage() {
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
    {
      id: "4",
      name: "Kampala International School",
      code: "kampala_intl",
      email: "admissions@kis.ug",
      is_active: true,
    },
  ]);

  const [search, setSearch] = React.useState("");
  const router = useRouter();

  const filteredSchools = schools.filter(
    (school) =>
      school.name.toLowerCase().includes(search.toLowerCase()) ||
      school.code.toLowerCase().includes(search.toLowerCase()) ||
      school.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Schools</h1>
          <p className="mt-1 text-slate-600">
            Manage all provisioned schools and tenants
          </p>
        </div>
        <Link href="/admin/tenants/new">
          <Button>Add New School</Button>
        </Link>
      </div>

      {/* Search */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
          <Input
            placeholder="Search by name, code, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
      </Card>

      {/* Schools Table */}
      <Card className="overflow-hidden">
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
              {filteredSchools.length > 0 ? (
                filteredSchools.map((school) => (
                  <TableRow key={school.id}>
                    <TableCell className="font-medium">{school.name}</TableCell>
                    <TableCell>{school.code}</TableCell>
                    <TableCell className="text-slate-600">{school.email}</TableCell>
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
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.push(`/admin/tenants/${school.id}`)}
                      >
                        Edit
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8">
                    <p className="text-slate-500">No schools found</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      <div className="text-sm text-slate-600">
        Showing {filteredSchools.length} of {schools.length} schools
      </div>
    </div>
  );
}
