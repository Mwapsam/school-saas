import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/app-shell";

export default function ParentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard role="parent">
      <AppShell role="parent">{children}</AppShell>
    </AuthGuard>
  );
}
