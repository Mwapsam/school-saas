import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/app-shell";

export default function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard role="teacher">
      <AppShell role="teacher">{children}</AppShell>
    </AuthGuard>
  );
}
