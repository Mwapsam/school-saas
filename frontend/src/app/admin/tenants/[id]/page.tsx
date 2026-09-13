"use client";

import React from "react";
import { useRouter, useParams } from "next/navigation";
import { SchoolForm } from "../../components/school-form";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

export default function EditSchoolPage() {
  const router = useRouter();
  const params = useParams();
  const schoolId = params.id as string;

  const [isLoading, setIsLoading] = React.useState(false);
  const [schoolData, setSchoolData] = React.useState<any>(null);
  const [isFetching, setIsFetching] = React.useState(true);

  React.useEffect(() => {
    // Fetch school data
    const fetchSchool = async () => {
      try {
        const response = await fetch(`/api/v1/schools/${schoolId}/`);
        if (!response.ok) {
          throw new Error("Failed to fetch school");
        }
        const data = await response.json();
        setSchoolData(data);
      } catch (error) {
        console.error("Error fetching school:", error);
        toast.error("Failed to load school data");
        router.push("/admin/tenants");
      } finally {
        setIsFetching(false);
      }
    };

    fetchSchool();
  }, [schoolId, router]);

  const handleSubmit = async (data: any) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/v1/schools/${schoolId}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error("Failed to update school");
      }

      const updated = await response.json();
      setSchoolData(updated);
      toast.success("School updated successfully!");
    } catch (error) {
      console.error("Error updating school:", error);
      toast.error("Failed to update school. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  if (isFetching) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-slate-600">Loading school data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.back()}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            {schoolData?.name || "Edit School"}
          </h1>
          <p className="mt-2 text-slate-600">
            Update school configuration and settings
          </p>
        </div>
      </div>

      {schoolData && (
        <SchoolForm
          initialData={schoolData}
          onSubmit={handleSubmit}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}
