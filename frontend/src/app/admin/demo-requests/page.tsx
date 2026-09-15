"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MoreHorizontal, Search } from "lucide-react";
import { toast } from "sonner";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/config";

interface DemoRequest {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  school_name: string;
  message: string;
  status: "pending" | "contacted" | "demo_scheduled" | "converted" | "rejected";
  converted_school: string | null;
  converted_school_code: string | null;
  created_at: string;
}

interface ConvertResult {
  status: string;
  school: {
    id: string;
    name: string;
    code: string;
    schema_name: string;
    domain: string;
    billing_status: string;
    trial_ends_at: string;
  };
  admin_user: {
    username: string;
    email: string;
    created: boolean;
    generated_password: string | null;
  };
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  contacted: "bg-blue-100 text-blue-800",
  demo_scheduled: "bg-purple-100 text-purple-800",
  converted: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

export default function DemoRequestsPage() {
  const [demoRequests, setDemoRequests] = React.useState<DemoRequest[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState("");

  const [convertTarget, setConvertTarget] = React.useState<DemoRequest | null>(null);
  const [convertSubmitting, setConvertSubmitting] = React.useState(false);
  const [convertForm, setConvertForm] = React.useState({
    code: "",
    schema_name: "",
    domain: "",
    trial_days: "14",
  });
  const [convertResult, setConvertResult] = React.useState<ConvertResult | null>(null);

  const loadRequests = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<DemoRequest[]>(API.demoRequests);
      setDemoRequests(data);
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to load demo requests"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const filteredRequests = demoRequests.filter(
    (req) =>
      req.full_name.toLowerCase().includes(search.toLowerCase()) ||
      req.email.toLowerCase().includes(search.toLowerCase()) ||
      req.school_name.toLowerCase().includes(search.toLowerCase())
  );

  const patchLocal = (id: string, patch: Partial<DemoRequest>) => {
    setDemoRequests((prev) =>
      prev.map((req) => (req.id === id ? { ...req, ...patch } : req))
    );
  };

  const runAction = async (
    id: string,
    url: string,
    nextStatus: DemoRequest["status"],
    successMessage: string
  ) => {
    try {
      await apiFetch(url, { method: "POST" });
      patchLocal(id, { status: nextStatus });
      toast.success(successMessage);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Action failed");
    }
  };

  const openConvertDialog = (request: DemoRequest) => {
    const base = slugify(request.school_name || request.full_name || "school");
    setConvertForm({
      code: base.toUpperCase(),
      schema_name: base || "school",
      domain: `${base || "school"}.pinewoodschoolzambia.com`,
      trial_days: "14",
    });
    setConvertResult(null);
    setConvertTarget(request);
  };

  const submitConvert = async () => {
    if (!convertTarget) return;
    setConvertSubmitting(true);
    try {
      const result = await apiFetch<ConvertResult>(
        API.demoRequestConvert(convertTarget.id),
        {
          method: "POST",
          body: {
            code: convertForm.code,
            schema_name: convertForm.schema_name,
            domain: convertForm.domain,
            trial_days: Number(convertForm.trial_days) || 14,
          },
        }
      );
      setConvertResult(result);
      patchLocal(convertTarget.id, {
        status: "converted",
        converted_school: result.school.id,
        converted_school_code: result.school.code,
      });
      toast.success(`${result.school.name} provisioned successfully`);
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to provision tenant"
      );
    } finally {
      setConvertSubmitting(false);
    }
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
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    <p className="text-slate-500">Loading…</p>
                  </TableCell>
                </TableRow>
              ) : filteredRequests.length > 0 ? (
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
                      {request.converted_school_code && (
                        <span className="ml-2 text-xs text-slate-500">
                          → {request.converted_school_code}
                        </span>
                      )}
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
                              runAction(
                                request.id,
                                API.demoRequestContact(request.id),
                                "contacted",
                                "Marked as contacted"
                              )
                            }
                          >
                            Mark as Contacted
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              runAction(
                                request.id,
                                API.demoRequestScheduleDemo(request.id),
                                "demo_scheduled",
                                "Demo scheduled"
                              )
                            }
                          >
                            Schedule Demo
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={!!request.converted_school}
                            onClick={() => openConvertDialog(request)}
                          >
                            Convert to Tenant…
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              runAction(
                                request.id,
                                API.demoRequestReject(request.id),
                                "rejected",
                                "Marked as rejected"
                              )
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

      <Dialog
        open={!!convertTarget}
        onOpenChange={(open) => {
          if (!open) {
            setConvertTarget(null);
            setConvertResult(null);
          }
        }}
      >
        <DialogContent>
          {convertResult ? (
            <>
              <DialogHeader>
                <DialogTitle>Tenant provisioned</DialogTitle>
                <DialogDescription>
                  {convertResult.school.name} is live on a {convertForm.trial_days}-day
                  trial. Share these credentials with the school — the password is
                  shown only once.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2 rounded-md bg-slate-50 p-4 text-sm">
                <p><span className="font-medium">Domain:</span> {convertResult.school.domain}</p>
                <p><span className="font-medium">Admin username:</span> {convertResult.admin_user.username}</p>
                <p><span className="font-medium">Admin email:</span> {convertResult.admin_user.email}</p>
                {convertResult.admin_user.generated_password && (
                  <p>
                    <span className="font-medium">Temporary password:</span>{" "}
                    <code className="rounded bg-slate-200 px-1.5 py-0.5">
                      {convertResult.admin_user.generated_password}
                    </code>
                  </p>
                )}
              </div>
              <DialogFooter>
                <Button
                  onClick={() => {
                    setConvertTarget(null);
                    setConvertResult(null);
                  }}
                >
                  Done
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Convert to tenant</DialogTitle>
                <DialogDescription>
                  Provisions a new school with a {convertForm.trial_days}-day trial
                  (billing stays manual — no charge happens here) and a first admin
                  account for {convertTarget?.email}.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="code">School code</Label>
                  <Input
                    id="code"
                    value={convertForm.code}
                    onChange={(e) =>
                      setConvertForm((f) => ({ ...f, code: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="schema_name">Schema name</Label>
                  <Input
                    id="schema_name"
                    value={convertForm.schema_name}
                    onChange={(e) =>
                      setConvertForm((f) => ({ ...f, schema_name: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="domain">Domain</Label>
                  <Input
                    id="domain"
                    value={convertForm.domain}
                    onChange={(e) =>
                      setConvertForm((f) => ({ ...f, domain: e.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="trial_days">Trial length (days)</Label>
                  <Input
                    id="trial_days"
                    type="number"
                    value={convertForm.trial_days}
                    onChange={(e) =>
                      setConvertForm((f) => ({ ...f, trial_days: e.target.value }))
                    }
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setConvertTarget(null)}>
                  Cancel
                </Button>
                <Button onClick={submitConvert} disabled={convertSubmitting}>
                  {convertSubmitting ? "Provisioning…" : "Provision tenant"}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
