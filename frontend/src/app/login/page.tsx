"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { GraduationCap } from "lucide-react";
import { toast } from "sonner";

import { config } from "@/lib/config";
import { ApiError } from "@/lib/api";
import { homeForRoles } from "@/lib/navigation";
import { useAuth, useHydrated, useLogin } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { ThemeToggle } from "@/components/theme-toggle";

const schema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const { isAuthenticated, roles, activeRole } = useAuth();
  const login = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  // Bounce already-authenticated users to their dashboard.
  React.useEffect(() => {
    if (hydrated && isAuthenticated && roles.length) {
      router.replace(homeForRoles(roles, activeRole));
    }
  }, [hydrated, isAuthenticated, roles, activeRole, router]);

  const onSubmit = handleSubmit(async (values) => {
    try {
      const res = await login.mutateAsync(values);
      toast.success(`Welcome back, ${res.user.full_name || res.user.username}`);
      router.replace(homeForRoles(res.roles ?? [res.role], res.roles?.[0] ?? res.role));
    } catch (err) {
      let message = "Unable to sign in. Please try again.";
      if (err instanceof ApiError) {
        const code =
          err.data && typeof err.data === "object" && "code" in err.data
            ? String((err.data as Record<string, unknown>).code)
            : null;
        if (err.status === 401) {
          message = "Incorrect username or password.";
        } else if (err.status === 426 || code === "upgrade_required") {
          message = "This app is out of date. Please update to the latest version to sign in.";
        } else if (code === "client_disabled") {
          message = err.message;
        } else {
          message = err.message;
        }
      }
      toast.error(message);
    }
  });

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-muted/40 p-4">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <GraduationCap className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              {config.appName}
            </h1>
            <p className="text-sm text-muted-foreground">
              Sign in to the parent &amp; teacher portal
            </p>
          </div>
        </div>

        <Card>
          <CardContent className="pt-6">
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  autoFocus
                  aria-invalid={!!errors.username}
                  {...register("username")}
                />
                {errors.username ? (
                  <p className="text-xs text-destructive">
                    {errors.username.message}
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={!!errors.password}
                  {...register("password")}
                />
                {errors.password ? (
                  <p className="text-xs text-destructive">
                    {errors.password.message}
                  </p>
                ) : null}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={login.isPending}
              >
                {login.isPending ? <Spinner /> : null}
                Sign in
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-2 text-center text-xs text-muted-foreground">
          <p>
            Forgot your password?{" "}
            <Link
              href="/forgot-password"
              className="font-medium underline hover:text-foreground"
            >
              Reset it here
            </Link>
          </p>
          <p>Trouble signing in? Contact your school administrator.</p>
        </div>
      </div>
    </div>
  );
}
