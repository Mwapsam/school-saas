import {
  type LucideIcon,
  CalendarCheck,
  ClipboardList,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Receipt,
  Trophy,
  Users,
  Wallet,
  Megaphone,
  Settings,
  Book,
  Barcode,
  Clock,
  Tag,
  Briefcase,
  FileSignature,
  UserCog,
  LogOut,
  Scale,
} from "lucide-react";

import type { Role } from "./types";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** When true, the item is rendered but disabled (roadmap placeholder). */
  comingSoon?: boolean;
  /**
   * Parent-portal feature key (Configuration → Feature Access). When set, the
   * item is hidden unless the user's `features` map has it enabled. Items with
   * no `feature` are always shown.
   */
  feature?: string;
}

export interface NavSection {
  heading?: string;
  items: NavItem[];
}

export const parentNav: NavSection[] = [
  {
    items: [
      { label: "Dashboard", href: "/parent/dashboard", icon: LayoutDashboard },
      { label: "Academic Results", href: "/parent/results", icon: GraduationCap, feature: "results" },
      { label: "Fees & Payments", href: "/parent/fees", icon: Wallet, feature: "fees" },
      { label: "Invoices", href: "/parent/invoices", icon: FileText, feature: "invoices" },
      { label: "Receipts", href: "/parent/receipts", icon: Receipt, feature: "fees" },
    ],
  },
  {
    items: [
      { label: "Announcements", href: "/parent/announcements", icon: Megaphone, feature: "announcements" },
    ],
  },
  {
    heading: "More",
    items: [
      { label: "Attendance", href: "/parent/attendance", icon: CalendarCheck, comingSoon: true, feature: "attendance" },
      { label: "Account Settings", href: "/parent/account", icon: Settings },
    ],
  },
];

export const teacherNav: NavSection[] = [
  {
    items: [
      { label: "Dashboard", href: "/teacher/dashboard", icon: LayoutDashboard },
      { label: "Attendance Register", href: "/teacher/attendance", icon: ClipboardList },
      { label: "Marks Entry", href: "/teacher/marks", icon: GraduationCap },
      { label: "Skills Assessment", href: "/teacher/skills", icon: ListChecks },
      { label: "Term Activities", href: "/teacher/activities", icon: Trophy },
    ],
  },
  {
    heading: "More",
    items: [
      { label: "My Classes", href: "/teacher/classes", icon: Users, comingSoon: true },
      { label: "Analytics", href: "/teacher/analytics", icon: LineChart, comingSoon: true },
      { label: "Account Settings", href: "/teacher/account", icon: Settings },
    ],
  },
];

export const librarianNav: NavSection[] = [
  {
    items: [
      { label: "Dashboard", href: "/librarian/dashboard", icon: LayoutDashboard },
      { label: "Book Catalog", href: "/librarian/books", icon: Book },
      { label: "Categories", href: "/librarian/categories", icon: Tag },
    ],
  },
  {
    heading: "Scanning",
    items: [
      { label: "Issue Book", href: "/librarian/scan-issue", icon: Barcode },
      { label: "Return Book", href: "/librarian/scan-return", icon: Barcode },
    ],
  },
  {
    heading: "Reports",
    items: [
      { label: "Overdue Books", href: "/librarian/overdue", icon: Clock },
      { label: "Issued Books", href: "/librarian/issued", icon: Book },
    ],
  },
  {
    heading: "More",
    items: [
      { label: "Account Settings", href: "/librarian/account", icon: Settings },
    ],
  },
];

export const hrNav: NavSection[] = [
  {
    items: [
      { label: "Dashboard", href: "/hr/dashboard", icon: LayoutDashboard },
      { label: "Employees", href: "/hr/employees", icon: Users },
      { label: "Recruitment", href: "/hr/recruitment", icon: Briefcase },
      { label: "Onboarding", href: "/hr/onboarding", icon: ListChecks },
      { label: "Contracts", href: "/hr/contracts", icon: FileSignature },
      { label: "Leave", href: "/hr/leave", icon: CalendarCheck },
      { label: "Attendance", href: "/hr/attendance", icon: ClipboardList },
      { label: "Performance", href: "/hr/performance", icon: LineChart },
      { label: "Training", href: "/hr/training", icon: GraduationCap },
      { label: "Employee Relations", href: "/hr/relations", icon: Scale },
      { label: "Employee Exit", href: "/hr/exit", icon: LogOut },
    ],
  },
  {
    heading: "Admin",
    items: [
      { label: "Payroll", href: "/hr/payroll", icon: Wallet },
      { label: "HR Tasks", href: "/hr/tasks", icon: ListChecks },
      { label: "Reports", href: "/hr/reports", icon: LineChart },
      { label: "Analytics", href: "/hr/analytics", icon: LineChart },
      { label: "Policies", href: "/hr/policies", icon: FileText },
      { label: "Audit Trail", href: "/hr/audit", icon: FileText },
      { label: "HR Settings", href: "/hr/settings", icon: Settings },
      { label: "Account Settings", href: "/hr/account", icon: Settings },
    ],
  },
];

/** Self-service block appended for any user with a linked employee profile. */
export const myHrNav: NavSection[] = [
  {
    heading: "My HR",
    items: [
      { label: "My Profile", href: "/my-hr/profile", icon: UserCog },
      { label: "My Leave", href: "/my-hr/leave", icon: CalendarCheck },
      { label: "My Attendance", href: "/my-hr/attendance", icon: ClipboardList },
      { label: "My Documents", href: "/my-hr/documents", icon: FileText },
      { label: "My Payslips", href: "/my-hr/payslips", icon: Wallet },
      { label: "My Reviews", href: "/my-hr/reviews", icon: LineChart },
      { label: "My Policies", href: "/my-hr/policies", icon: FileText },
    ],
  },
];

export function navForRole(role: Role): NavSection[] {
  if (role === "teacher") return teacherNav;
  if (role === "parent") return parentNav;
  if (role === "librarian") return librarianNav;
  if (role === "hr") return hrNav;
  return [];
}

const ROLE_ORDER: Role[] = ["hr", "teacher", "librarian", "parent"];
const ROLE_AREA: Partial<Record<Role, string>> = {
  hr: "Human Resources",
  teacher: "Teaching",
  librarian: "Library",
  parent: "My Children",
};

/**
 * Merge the navigation for every role a user holds into one sidebar. Each role's
 * sections are grouped under an area heading; a shared trailing item (Account
 * Settings) is de-duplicated and kept once at the end. The active role is
 * ordered first so its sections lead.
 */
export function navForRoles(roles: Role[], activeRole?: Role | null): NavSection[] {
  const held = ROLE_ORDER.filter((r) => roles.includes(r));
  if (held.length <= 1) return navForRole(held[0] ?? roles[0] ?? "unknown");

  const ordered = activeRole && held.includes(activeRole)
    ? [activeRole, ...held.filter((r) => r !== activeRole)]
    : held;

  const out: NavSection[] = [];
  const seenHrefs = new Set<string>();
  let account: NavItem | undefined;

  for (const role of ordered) {
    const sections = navForRole(role);
    sections.forEach((section, idx) => {
      const items = section.items.filter((item) => {
        if (item.href.endsWith("/account")) {
          account = account ?? { ...item, label: "Account Settings" };
          return false;
        }
        if (seenHrefs.has(item.href)) return false;
        seenHrefs.add(item.href);
        return true;
      });
      if (!items.length) return;
      out.push({
        heading: idx === 0 ? ROLE_AREA[role] : section.heading,
        items,
      });
    });
  }

  if (account) out.push({ heading: "More", items: [account] });
  return out;
}

/**
 * Drop nav items whose `feature` is disabled in the user's Feature Access map.
 * A missing map (older session, non-parent) leaves every item visible.
 * Sections left with no items are removed.
 */
export function filterNavByFeatures(
  sections: NavSection[],
  features?: Record<string, boolean> | null,
): NavSection[] {
  if (!features) return sections;
  return sections
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) => !item.feature || features[item.feature] !== false,
      ),
    }))
    .filter((section) => section.items.length > 0);
}

export function homeForRole(role: Role): string {
  if (role === "hr") return "/hr/dashboard";
  if (role === "teacher") return "/teacher/dashboard";
  if (role === "parent") return "/parent/dashboard";
  if (role === "librarian") return "/librarian/dashboard";
  return "/login";
}

/** Landing route for a multi-role user: the active role's home, else the first
 *  portal role's home. */
export function homeForRoles(roles: Role[], activeRole?: Role | null): string {
  if (activeRole && roles.includes(activeRole)) return homeForRole(activeRole);
  const first = ROLE_ORDER.find((r) => roles.includes(r)) ?? roles[0];
  return first ? homeForRole(first) : "/login";
}
