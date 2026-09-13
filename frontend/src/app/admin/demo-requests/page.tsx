"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Search } from "lucide-react";
import { toast } from "sonner";

interface DemoRequest {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  school_name: string;
  message: string;
  status: "pending" | "contacted" | "demo_scheduled" | "converted" | "rejected";
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  contacted: "bg-blue-100 text-blue-800",
  demo_scheduled: "bg-purple-100 text-purple-800",
  converted: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

const DEMO_REQUESTS: DemoRequest[] = [
  {
    id: "1",
    full_name: "John Mwangi",
    email: "john@example.com",
    phone: "+254 712 345 678",
    school_name: "Westlands Academy",
    message: "Interested in demo for our school",
    status: "pending",
    created_at: "2026-09-13T10:30:00Z",
  },
  {
    id: "2",
    full_name: "Jane Kamau",
    email: "jane@example.com",
    phone: "+254 722 987 654",
    school_name: "Upper Hill School",
    message: "Want to see features",
    status: "contacted",
    created_at: "2026-09-12T14:20:00Z",
  },
  {
    id: "3",
    full_name: "Michael Ochieng",
    email: "michael@example.com",
    phone: "+254 734 567 890",
    school_name: "Aga Khan Academy",
    message: "Scheduling a demo",
    status: "demo_scheduled",
    created_at: "2026-09-11T09:15:00Z",
  },
  {
    id: "4",
    full_name: "Sarah Kipchoge",
    email: "sarah@example.com",
    phone: "+254 700 111 222",
    school_name: "Alliance High School",
    message: "Great product, moving forward",
    status: "converted",
    created_at: "2026-09-10T16:45:00Z",
  },
];

export default function DemoRequestsPage() {
  const [demoRequests, setDemoRequests] = React.useState<DemoRequest[]>(DEMO_REQUESTS);
  const [search, setSearch] = React.useState("");

  const filteredRequests = demoRequests.filter(
    (req) =>
      req.full_name.toLowerCase().includes(search.toLowerCase()) ||
      req.email.toLowerCase().includes(search.toLowerCase()) ||
      req.school_name.toLowerCase().includes(search.toLowerCase())
  );

  const updateStatus = (id: string, newStatus: DemoRequest["status"]) => {
    setDemoRequests(
      demoRequests.map((req) =>
        req.id === id ? { ...req, status: newStatus } : req
      )
    );
    toast.success("Status updated");
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const pendingCount = demoRequests.filter(
    (req) => req.status === "pending"
  ).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Demo Requests</h1>
        <p className="mt-2 text-slate-600">
          Manage prospective customer demo requests
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs font-medium uppercase text-slate-600">Total Requests</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {demoRequests.length}
          </p>
        </Card>
        <Card className="p-4 border-yellow-200 bg-yellow-50">
          <p className="text-xs font-medium uppercase text-yellow-700">Pending</p>
          <p className="mt-2 text-2xl font-bold text-yellow-900">
            {pendingCount}
          </p>
        </Card>
        <Card className="p-4 border-green-200 bg-green-50">
          <p className="text-xs font-medium uppercase text-green-700">Converted</p>
          <p className="mt-2 text-2xl font-bold text-green-900">
            {demoRequests.filter((r) => r.status === "converted").length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs font-medium uppercase text-slate-600">
            Conversion Rate
          </p>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {demoRequests.length > 0
              ? Math.round(
                  (demoRequests.filter((r) => r.status === "converted").length /
                    demoRequests.length) *
                    100
                )
              : 0}
            %
          </p>
        </Card>
      </div>

      {/* Search */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
          <Input
            placeholder="Search by name, email, or school..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
      </Card>

      {/* Requests Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>School</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRequests.length > 0 ? (
                filteredRequests.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-medium">
                      {request.full_name}
                    </TableCell>
                    <TableCell className="text-slate-600">
                      {request.email}
                    </TableCell>
                    <TableCell>{request.school_name}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          STATUS_COLORS[request.status]
                        }`}
                      >
                        {request.status.replace(/_/g, " ")}
                      </span>
                    </TableCell>
                    <TableCell className="text-slate-600">
                      {formatDate(request.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() =>
                              updateStatus(request.id, "contacted")
                            }
                          >
                            Mark as Contacted
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              updateStatus(request.id, "demo_scheduled")
                            }
                          >
                            Schedule Demo
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              updateStatus(request.id, "converted")
                            }
                          >
                            Mark as Converted
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              updateStatus(request.id, "rejected")
                            }
                          >
                            Reject
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    <p className="text-slate-500">No demo requests found</p>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
