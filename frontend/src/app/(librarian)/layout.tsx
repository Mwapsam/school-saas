import { AuthGuard } from "@/components/auth-guard";
import { AppShell } from "@/components/app-shell";

export default function LibrarianLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard role="librarian">
      <AppShell role="librarian">{children}</AppShell>
    </AuthGuard>
  );
}
