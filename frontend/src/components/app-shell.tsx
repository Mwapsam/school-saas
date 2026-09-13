"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import { LogOut, Menu, User as UserIcon, ChevronsUpDown } from "lucide-react";

import { config } from "@/lib/config";
import {
  navForRoles,
  filterNavByFeatures,
  homeForRole,
  myHrNav,
  type NavSection,
} from "@/lib/navigation";
import { useAuth, useLogout } from "@/hooks/use-auth";
import { useAuthStore } from "@/lib/auth-store";
import { useSchoolConfig } from "@/hooks/useSchoolConfig";
import { cn, initials } from "@/lib/utils";
import type { Role } from "@/lib/types";

const ROLE_LABEL: Record<string, string> = {
  teacher: "Teacher",
  parent: "Parent",
  librarian: "Librarian",
  hr: "HR",
  admin: "Admin",
  student: "Student",
  unknown: "User",
};
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/theme-toggle";

function NavLinks({
  sections,
  pathname,
  onNavigate,
}: {
  sections: NavSection[];
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4" aria-label="Primary">
      {sections.map((section, i) => (
        <div key={i} className="space-y-1">
          {section.heading ? (
            <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wider text-sidebar-foreground/50">
              {section.heading}
            </p>
          ) : null}
          {section.items.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            if (item.comingSoon) {
              return (
                <span
                  key={item.href}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground/40"
                  aria-disabled
                >
                  <Icon className="h-4 w-4" />
                  <span className="flex-1">{item.label}</span>
                  <Badge variant="outline" className="border-sidebar-border text-sidebar-foreground/50 text-[10px]">
                    Soon
                  </Badge>
                </span>
              );
            }
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/75 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function Brand() {
  const { data: schoolConfig } = useSchoolConfig();
  const schoolName = schoolConfig?.name || config.appName;
  const schoolLogo = schoolConfig?.logo_url || "/logo.png";
  const schoolAlt = schoolConfig?.name || "School Logo";

  return (
    <div className="flex items-center gap-3 px-5 py-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-white/10 p-0.5">
        <Image
          src={schoolLogo}
          alt={schoolAlt}
          width={36}
          height={36}
          className="object-contain"
          priority
          onError={(e) => {
            (e.target as HTMLImageElement).src = "/logo.png";
          }}
        />
      </div>
      <div className="min-w-0 leading-tight">
        <p className="truncate text-sm font-semibold text-sidebar-foreground">
          {schoolName}
        </p>
        <p className="text-xs text-sidebar-foreground/55">
          {schoolConfig?.description || "School Portal"}
        </p>
      </div>
    </div>
  );
}

export function AppShell({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, roles } = useAuth();
  const setActiveRole = useAuthStore((s) => s.setActiveRole);
  const logout = useLogout();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  // The area the user is currently in (from the route group) leads the sidebar.
  const sections = React.useMemo(() => {
    const base = filterNavByFeatures(navForRoles(roles, role), user?.features);
    // "My HR" self-service is offered to any staff member with a linked
    // employee record, regardless of their portal role — but not inside the
    // HR portal itself, where the same data is reached through the main nav.
    if (user?.has_employee_profile && role !== "hr") {
      return [...base, ...myHrNav];
    }
    return base;
  }, [roles, role, user?.features, user?.has_employee_profile]);

  const onLogout = () => {
    logout();
    router.replace("/login");
  };

  const switchRole = (next: Role) => {
    setActiveRole(next);
    router.push(homeForRole(next));
  };

  const roleLabel = ROLE_LABEL[role] ?? "User";
  const otherRoles = roles.filter((r) => r !== role);

  return (
    <div className="flex min-h-screen bg-muted/30">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
        <Brand />
        <NavLinks sections={sections} pathname={pathname} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur sm:px-6">
          {/* Mobile menu */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="bg-sidebar p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <Brand />
              <NavLinks
                sections={sections}
                pathname={pathname}
                onNavigate={() => setMobileOpen(false)}
              />
            </SheetContent>
          </Sheet>

          <div className="flex-1" />

          {otherRoles.length > 0 ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  <span className="text-xs text-muted-foreground">Viewing as</span>
                  <span className="font-medium">{roleLabel}</span>
                  <ChevronsUpDown className="h-3.5 w-3.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuLabel>Switch portal</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {roles.map((r) => (
                  <DropdownMenuItem
                    key={r}
                    onClick={() => switchRole(r)}
                    aria-current={r === role ? "true" : undefined}
                    className={cn(r === role && "font-semibold")}
                  >
                    {ROLE_LABEL[r] ?? r}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}

          <ThemeToggle />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="h-11 gap-2 px-2"
                aria-label="Account menu"
              >
                <Avatar className="h-8 w-8">
                  <AvatarFallback>
                    {initials(user?.full_name ?? "U")}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden text-left sm:block">
                  <span className="block text-sm font-medium leading-none">
                    {user?.full_name ?? "User"}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {roleLabel}
                  </span>
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <p className="text-sm font-medium">{user?.full_name}</p>
                <p className="text-xs font-normal text-muted-foreground">
                  {user?.email ?? user?.username}
                </p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href={`/${role}/account`}>
                  <UserIcon className="mr-2" /> Profile
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onLogout}>
                <LogOut className="mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
