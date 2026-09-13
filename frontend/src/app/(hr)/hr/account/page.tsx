"use client";

import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/page-header";
import { AccountSettingsForm } from "@/components/account-settings-form";

export default function HRAccountPage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <>
      <PageHeader
        title="Account Settings"
        description="Manage your account and security preferences."
      />
      <AccountSettingsForm user={user} />
    </>
  );
}
