"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { SchoolForm } from "../../components/school-form";
import { toast } from "sonner";

export default function NewSchoolPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);

  const handleSubmit = async (data: any) => {
    setIsLoading(true);
    try {
      // Call API to create school
      const response = await fetch("/api/v1/schools/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error("Failed to create school");
      }

      const school = await response.json();
      toast.success("School created successfully!");
      router.push(`/admin/tenants/${school.id}`);
    } catch (error) {
      console.error("Error creating school:", error);
      toast.error("Failed to create school. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Create New School</h1>
        <p className="mt-2 text-slate-600">
          Provision a new tenant with initial configuration
        </p>
      </div>

      <SchoolForm onSubmit={handleSubmit} isLoading={isLoading} />
    </div>
  );
}
