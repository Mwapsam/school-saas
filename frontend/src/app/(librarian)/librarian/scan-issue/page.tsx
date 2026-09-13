"use client";

import { useState } from "react";
import { Barcode } from "lucide-react";
import { toast } from "sonner";

import {
  useLibrarianScanLookup,
  useLibrarianScanIssue,
  useLibrarianBatches,
  useLibrarianBatchStudents,
} from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type BorrowerType = "student" | "staff";

export default function ScanIssuePage() {
  const [barcode, setBarcode] = useState<string>("");
  const [dueDays, setDueDays] = useState<string>("14");

  const [borrowerType, setBorrowerType] = useState<BorrowerType>("student");
  const [batchId, setBatchId] = useState<string>("");
  const [studentId, setStudentId] = useState<string>("");
  const [staffId, setStaffId] = useState<string>("");

  const scanLookup = useLibrarianScanLookup();
  const scanIssue = useLibrarianScanIssue();
  const { data: batches, isLoading: batchesLoading } = useLibrarianBatches();
  const { data: students, isLoading: studentsLoading } =
    useLibrarianBatchStudents(batchId || undefined);

  const handleScanLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!barcode.trim()) return;
    try {
      const book = await scanLookup.mutateAsync(barcode);
      toast.success(`Found: ${book.title} (${book.available_copies} available)`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Book not found");
    }
  };

  const borrowerReady =
    borrowerType === "student" ? !!studentId : !!staffId.trim();

  const handleIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!barcode.trim()) {
      toast.error("Scan or enter a book barcode first");
      return;
    }
    if (!borrowerReady) {
      toast.error(
        borrowerType === "student"
          ? "Pick a class and a pupil"
          : "Enter the staff member's ID",
      );
      return;
    }

    try {
      await scanIssue.mutateAsync({
        barcode,
        due_days: parseInt(dueDays) || 14,
        ...(borrowerType === "student"
          ? { student_id: studentId }
          : { employee_id: staffId.trim() }),
      });
      toast.success("Book issued successfully");
      setBarcode("");
      setStudentId("");
      setStaffId("");
      setDueDays("14");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to issue book");
    }
  };

  return (
    <>
      <PageHeader
        title="Issue Book"
        description="Scan a book barcode and pick the borrower from their class."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Scan Barcode</CardTitle>
            <CardDescription>
              Scan a book barcode to look up the book details.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleScanLookup} className="space-y-4">
              <div>
                <Label htmlFor="barcode">Barcode</Label>
                <div className="relative mt-2">
                  <Barcode className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="barcode"
                    placeholder="Scan or enter barcode..."
                    className="pl-9"
                    value={barcode}
                    onChange={(e) => setBarcode(e.target.value)}
                    autoFocus
                  />
                </div>
              </div>
              <Button
                type="submit"
                disabled={scanLookup.isPending || !barcode.trim()}
              >
                {scanLookup.isPending ? "Scanning..." : "Lookup"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Issue Details</CardTitle>
            <CardDescription>
              Choose the borrower and the due date.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleIssue} className="space-y-4">
              <div>
                <Label>Borrower</Label>
                <div className="mt-2 inline-flex rounded-md border p-0.5 text-sm">
                  {(["student", "staff"] as BorrowerType[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setBorrowerType(t)}
                      className={
                        "rounded px-3 py-1 capitalize transition-colors " +
                        (borrowerType === t
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:text-foreground")
                      }
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {borrowerType === "student" ? (
                <>
                  <div>
                    <Label>Class</Label>
                    <Select
                      value={batchId}
                      onValueChange={(v) => {
                        setBatchId(v);
                        setStudentId("");
                      }}
                    >
                      <SelectTrigger className="mt-2">
                        <SelectValue
                          placeholder={
                            batchesLoading ? "Loading…" : "Select a class"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {(batches ?? []).map((b) => (
                          <SelectItem key={b.id} value={b.id}>
                            {b.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Pupil</Label>
                    <Select
                      value={studentId}
                      onValueChange={setStudentId}
                      disabled={!batchId || studentsLoading}
                    >
                      <SelectTrigger className="mt-2">
                        <SelectValue
                          placeholder={
                            !batchId
                              ? "Pick a class first"
                              : studentsLoading
                                ? "Loading…"
                                : "Select a pupil"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {(students ?? []).map((s) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.full_name} · {s.admission_no}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </>
              ) : (
                <div>
                  <Label htmlFor="staff-id">Staff member ID</Label>
                  <Input
                    id="staff-id"
                    placeholder="Employee ID"
                    className="mt-2"
                    value={staffId}
                    onChange={(e) => setStaffId(e.target.value)}
                  />
                </div>
              )}

              <div>
                <Label htmlFor="due-days">Due in (days)</Label>
                <Input
                  id="due-days"
                  type="number"
                  min="1"
                  className="mt-2"
                  value={dueDays}
                  onChange={(e) => setDueDays(e.target.value)}
                />
              </div>
              <Button
                type="submit"
                disabled={
                  scanIssue.isPending || !barcode.trim() || !borrowerReady
                }
              >
                {scanIssue.isPending ? "Issuing..." : "Issue Book"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
