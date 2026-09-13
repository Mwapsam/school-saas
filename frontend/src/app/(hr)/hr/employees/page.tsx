"use client";

import * as React from "react";
import Link from "next/link";

import { toast } from "sonner";

import { useHREmployees, useCreateEmployee, useHRCan, useHRLookup } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  active: "default",
  probation: "secondary",
  on_leave: "outline",
  suspended: "destructive",
  notice_period: "destructive",
  exited: "outline",
};

export default function HREmployeesPage() {
  const [q, setQ] = React.useState("");
  const [staffType, setStaffType] = React.useState("all");
  const [empStatus, setEmpStatus] = React.useState("all");
  const [department, setDepartment] = React.useState("all");
  const [category, setCategory] = React.useState("all");
  const [position, setPosition] = React.useState("all");
  const [grade, setGrade] = React.useState("all");
  const [contractType, setContractType] = React.useState("all");
  const [joinedFrom, setJoinedFrom] = React.useState("");
  const [joinedTo, setJoinedTo] = React.useState("");
  const [page, setPage] = React.useState(1);

  const departments = useHRLookup("department").data ?? [];
  const categories = useHRLookup("category").data ?? [];
  const positions = useHRLookup("position").data ?? [];
  const grades = useHRLookup("grade").data ?? [];

  const params: Record<string, string> = { page: String(page) };
  if (q) params.q = q;
  if (staffType !== "all") params.staff_type = staffType;
  if (empStatus !== "all") params.employment_status = empStatus;
  if (department !== "all") params.department = department;
  if (category !== "all") params.category = category;
  if (position !== "all") params.position = position;
  if (grade !== "all") params.grade = grade;
  if (contractType !== "all") params.contract_type = contractType;
  if (joinedFrom) params.joined_from = joinedFrom;
  if (joinedTo) params.joined_to = joinedTo;

  const reset = () => setPage(1);

  const { data, isLoading, isError, refetch } = useHREmployees(params);
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Employees"
        description="The central staff directory."
        actions={<AddEmployeeDialog />}
      />

      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search name or employee number…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          className="max-w-xs"
        />
        <Select value={staffType} onValueChange={(v) => { setStaffType(v); setPage(1); }}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All staff</SelectItem>
            <SelectItem value="teaching">Teaching</SelectItem>
            <SelectItem value="non_teaching">Non-teaching</SelectItem>
          </SelectContent>
        </Select>
        <Select value={empStatus} onValueChange={(v) => { setEmpStatus(v); reset(); }}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="probation">Probation</SelectItem>
            <SelectItem value="on_leave">On leave</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
            <SelectItem value="notice_period">Notice period</SelectItem>
            <SelectItem value="exited">Exited</SelectItem>
          </SelectContent>
        </Select>

        <Select value={department} onValueChange={(v) => { setDepartment(v); reset(); }}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Department" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any department</SelectItem>
            {departments.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={category} onValueChange={(v) => { setCategory(v); reset(); }}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any category</SelectItem>
            {categories.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={position} onValueChange={(v) => { setPosition(v); reset(); }}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Position" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any position</SelectItem>
            {positions.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={grade} onValueChange={(v) => { setGrade(v); reset(); }}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Grade" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any grade</SelectItem>
            {grades.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={contractType} onValueChange={(v) => { setContractType(v); reset(); }}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Contract" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any contract</SelectItem>
            <SelectItem value="permanent">Permanent</SelectItem>
            <SelectItem value="fixed_term">Fixed term</SelectItem>
            <SelectItem value="probation">Probation</SelectItem>
            <SelectItem value="temporary">Temporary</SelectItem>
            <SelectItem value="casual">Casual</SelectItem>
            <SelectItem value="consultant">Consultant</SelectItem>
            <SelectItem value="intern">Intern</SelectItem>
          </SelectContent>
        </Select>
        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          Joined
          <Input type="date" className="h-9 w-36" value={joinedFrom}
            onChange={(e) => { setJoinedFrom(e.target.value); reset(); }} />
          –
          <Input type="date" className="h-9 w-36" value={joinedTo}
            onChange={(e) => { setJoinedTo(e.target.value); reset(); }} />
        </label>
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-96" />
      ) : rows.length === 0 ? (
        <EmptyState title="No employees found" description="Try a different search or filter." />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Emp No</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Position</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-mono text-xs">{e.employee_number}</TableCell>
                    <TableCell>
                      <Link href={`/hr/employees/${e.id}`} className="font-medium hover:underline">
                        {e.full_name}
                      </Link>
                    </TableCell>
                    <TableCell>{e.department ?? "—"}</TableCell>
                    <TableCell>{e.position ?? e.job_title ?? "—"}</TableCell>
                    <TableCell>{e.is_teaching_staff ? "Teaching" : "Non-teaching"}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[e.employment_status] ?? "outline"}>
                        {e.employment_status.replace("_", " ")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{data?.count ?? 0} employees</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={!data?.previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={!data?.next}
                onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function AddEmployeeDialog() {
  const canManage = useHRCan("hr.employee.manage");
  const create = useCreateEmployee();
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    employee_number: "",
    first_name: "",
    last_name: "",
    joining_date: "",
    gender: "true",
    is_teaching_staff: "false",
    job_title: "",
    email: "",
  });

  if (!canManage) return null;

  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add employee</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New employee</DialogTitle></DialogHeader>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(
              {
                ...f,
                gender: f.gender === "true",
                is_teaching_staff: f.is_teaching_staff === "true",
              },
              {
                onSuccess: () => { setOpen(false); toast.success("Employee created"); },
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              },
            );
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="en">Employee number</Label>
            <Input id="en" required value={f.employee_number} onChange={(e) => set("employee_number", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="jd">Joining date</Label>
            <Input id="jd" type="date" required value={f.joining_date} onChange={(e) => set("joining_date", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="fn">First name</Label>
            <Input id="fn" required value={f.first_name} onChange={(e) => set("first_name", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ln">Last name</Label>
            <Input id="ln" required value={f.last_name} onChange={(e) => set("last_name", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="jt">Job title</Label>
            <Input id="jt" value={f.job_title} onChange={(e) => set("job_title", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="em">Email</Label>
            <Input id="em" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Gender</Label>
            <Select value={f.gender} onValueChange={(v) => set("gender", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="true">Male</SelectItem>
                <SelectItem value="false">Female</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Staff type</Label>
            <Select value={f.is_teaching_staff} onValueChange={(v) => set("is_teaching_staff", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="false">Non-teaching</SelectItem>
                <SelectItem value="true">Teaching</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" disabled={create.isPending}>Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
