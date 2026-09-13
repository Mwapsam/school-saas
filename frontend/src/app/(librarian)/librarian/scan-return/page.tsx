"use client";

import { useState } from "react";
import { Barcode } from "lucide-react";
import { toast } from "sonner";

import { useLibrarianScanLookup, useLibrarianScanReturn } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function ScanReturnPage() {
  const [barcode, setBarcode] = useState<string>("");

  const scanLookup = useLibrarianScanLookup();
  const scanReturn = useLibrarianScanReturn();

  const handleScanLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!barcode.trim()) return;

    try {
      const book = await scanLookup.mutateAsync(barcode);
      toast.success(`Found: ${book.title}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Book not found");
    }
  };

  const handleReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!barcode.trim()) {
      toast.error("Please scan a barcode");
      return;
    }

    try {
      await scanReturn.mutateAsync({ barcode });
      toast.success("Book returned successfully");
      setBarcode("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to return book");
    }
  };

  return (
    <>
      <PageHeader
        title="Return Book"
        description="Scan a book barcode to process its return."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Scan Barcode</CardTitle>
            <CardDescription>
              Scan the book barcode to look up and process the return.
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
            <CardTitle className="text-base">Process Return</CardTitle>
            <CardDescription>
              Confirm the book return.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleReturn} className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {barcode ? (
                  <>Barcode: <span className="font-mono">{barcode}</span></>
                ) : (
                  "Scan a barcode above"
                )}
              </p>
              <Button
                type="submit"
                disabled={scanReturn.isPending || !barcode.trim()}
                className="w-full"
              >
                {scanReturn.isPending ? "Processing..." : "Confirm Return"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
