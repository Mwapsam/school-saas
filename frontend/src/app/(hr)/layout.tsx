import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/app-shell";

export default function HRLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard role="hr">
      <AppShell role="hr">{children}</AppShell>
    </AuthGuard>
  );
}
