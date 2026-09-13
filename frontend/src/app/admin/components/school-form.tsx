"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";

interface SchoolFormData {
  name: string;
  code: string;
  email: string;
  phone: string;
  description: string;
  website: string;
  primary_color: string;
  secondary_color: string;
  address_line1: string;
  city: string;
  state: string;
  timezone: string;
  is_active: boolean;
  admission_enabled: boolean;
  features: {
    parent_portal: boolean;
    teacher_portal: boolean;
    librarian_portal: boolean;
    hr_portal: boolean;
    admission_portal: boolean;
  };
  social_links: {
    twitter?: string;
    facebook?: string;
    instagram?: string;
    linkedin?: string;
  };
}

interface SchoolFormProps {
  initialData?: Partial<SchoolFormData>;
  onSubmit: (data: SchoolFormData) => void;
  isLoading?: boolean;
}

const defaultFormData: SchoolFormData = {
  name: "",
  code: "",
  email: "",
  phone: "",
  description: "",
  website: "",
  primary_color: "#1a7a3c",
  secondary_color: "#f5f5f5",
  address_line1: "",
  city: "",
  state: "",
  timezone: "UTC",
  is_active: true,
  admission_enabled: false,
  features: {
    parent_portal: true,
    teacher_portal: true,
    librarian_portal: true,
    hr_portal: true,
    admission_portal: false,
  },
  social_links: {},
};

export function SchoolForm({
  initialData,
  onSubmit,
  isLoading = false,
}: SchoolFormProps) {
  const [formData, setFormData] = useState<SchoolFormData>({
    ...defaultFormData,
    ...initialData,
  });

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >
  ) => {
    const { name, value, type } = e.target as HTMLInputElement;
    if (type === "checkbox") {
      const checked = (e.target as HTMLInputElement).checked;
      if (name.startsWith("features.")) {
        const feature = name.split(".")[1] as keyof typeof formData.features;
        setFormData({
          ...formData,
          features: { ...formData.features, [feature]: checked },
        });
      } else {
        setFormData({ ...formData, [name]: checked });
      }
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Info */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          Basic Information
        </h3>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="name">School Name</Label>
              <Input
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="e.g., Pinewood Preparatory School"
                required
              />
            </div>
            <div>
              <Label htmlFor="code">School Code</Label>
              <Input
                id="code"
                name="code"
                value={formData.code}
                onChange={handleChange}
                placeholder="e.g., pinewood"
                disabled={!!initialData}
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="description">Description / Mission Statement</Label>
            <Textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              placeholder="Brief description of the school"
              rows={3}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="office@school.edu"
              />
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="+254 712 345 678"
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="website">Website</Label>
              <Input
                id="website"
                name="website"
                type="url"
                value={formData.website}
                onChange={handleChange}
                placeholder="https://school.edu"
              />
            </div>
            <div>
              <Label htmlFor="timezone">Timezone</Label>
              <select
                id="timezone"
                name="timezone"
                value={formData.timezone}
                onChange={handleChange}
                className="flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:border-slate-900 focus:outline-none"
              >
                <option value="UTC">UTC</option>
                <option value="Africa/Nairobi">Africa/Nairobi</option>
                <option value="Africa/Lusaka">Africa/Lusaka</option>
                <option value="America/New_York">America/New_York</option>
                <option value="Europe/London">Europe/London</option>
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* Address */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Address</h3>
        <div className="space-y-4">
          <div>
            <Label htmlFor="address_line1">Address Line 1</Label>
            <Input
              id="address_line1"
              name="address_line1"
              value={formData.address_line1}
              onChange={handleChange}
              placeholder="Street address"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                name="city"
                value={formData.city}
                onChange={handleChange}
                placeholder="City"
              />
            </div>
            <div>
              <Label htmlFor="state">State/Province</Label>
              <Input
                id="state"
                name="state"
                value={formData.state}
                onChange={handleChange}
                placeholder="State/Province"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Branding */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Branding</h3>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="primary_color">Primary Color</Label>
              <div className="flex gap-2">
                <Input
                  id="primary_color"
                  name="primary_color"
                  type="color"
                  value={formData.primary_color}
                  onChange={handleChange}
                  className="h-10 w-20 cursor-pointer rounded border"
                />
                <Input
                  type="text"
                  value={formData.primary_color}
                  onChange={handleChange}
                  name="primary_color"
                  placeholder="#1a7a3c"
                  className="flex-1"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="secondary_color">Secondary Color</Label>
              <div className="flex gap-2">
                <Input
                  id="secondary_color"
                  name="secondary_color"
                  type="color"
                  value={formData.secondary_color}
                  onChange={handleChange}
                  className="h-10 w-20 cursor-pointer rounded border"
                />
                <Input
                  type="text"
                  value={formData.secondary_color}
                  onChange={handleChange}
                  name="secondary_color"
                  placeholder="#f5f5f5"
                  className="flex-1"
                />
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Features */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Features</h3>
        <div className="space-y-3">
          {(
            [
              "parent_portal",
              "teacher_portal",
              "librarian_portal",
              "hr_portal",
              "admission_portal",
            ] as const
          ).map((feature) => (
            <div key={feature} className="flex items-center space-x-2">
              <Checkbox
                id={`features.${feature}`}
                name={`features.${feature}`}
                checked={formData.features[feature]}
                onChange={handleChange}
              />
              <Label
                htmlFor={`features.${feature}`}
                className="cursor-pointer capitalize"
              >
                {feature.replace(/_/g, " ")}
              </Label>
            </div>
          ))}
        </div>
      </Card>

      {/* Admission */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Admission</h3>
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="admission_enabled"
              name="admission_enabled"
              checked={formData.admission_enabled}
              onChange={handleChange}
            />
            <Label htmlFor="admission_enabled" className="cursor-pointer">
              Enable Admission Portal
            </Label>
          </div>
        </div>
      </Card>

      {/* Status */}
      <Card className="p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-900">Status</h3>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="is_active"
            name="is_active"
            checked={formData.is_active}
            onChange={handleChange}
          />
          <Label htmlFor="is_active" className="cursor-pointer">
            School is Active
          </Label>
        </div>
      </Card>

      {/* Submit */}
      <div className="flex gap-4">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Saving..." : "Save School"}
        </Button>
      </div>
    </form>
  );
}
