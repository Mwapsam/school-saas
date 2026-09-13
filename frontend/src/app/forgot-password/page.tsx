"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, GraduationCap, Mail } from "lucide-react";
import { toast } from "sonner";

import { config } from "@/lib/config";
import { ApiError } from "@/lib/api";
import { usePasswordResetRequest } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { ThemeToggle } from "@/components/theme-toggle";

const schema = z.object({
  email: z.string().email("Please enter a valid email address"),
});

type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [submitted, setSubmitted] = React.useState(false);
  const requestReset = usePasswordResetRequest();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await requestReset.mutateAsync(values);
      setSubmitted(true);
      toast.success("Check your email for password reset instructions.");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not send reset email.";
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
              Reset your password
            </p>
          </div>
        </div>

        <Card>
          <CardContent className="pt-6">
            {submitted ? (
              <div className="space-y-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 mx-auto">
                  <Mail className="h-6 w-6" />
                </div>
                <div className="text-center space-y-2">
                  <p className="font-medium">Check your email</p>
                  <p className="text-sm text-muted-foreground">
                    We&apos;ve sent password reset instructions to your email address.
                    Follow the link to set a new password.
                  </p>
                </div>
                <Button asChild className="w-full">
                  <Link href="/login">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to login
                  </Link>
                </Button>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="space-y-4" noValidate>
                <div className="text-sm text-muted-foreground mb-4">
                  Enter the email address associated with your account, and we&apos;ll
                  send you a link to reset your password.
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    autoFocus
                    aria-invalid={!!errors.email}
                    {...register("email")}
                  />
                  {errors.email ? (
                    <p className="text-xs text-destructive">
                      {errors.email.message}
                    </p>
                  ) : null}
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={requestReset.isPending}
                >
                  {requestReset.isPending ? <Spinner /> : null}
                  Send reset link
                </Button>

                <div className="pt-2 text-center text-xs">
                  <Link
                    href="/login"
                    className="text-muted-foreground hover:text-foreground underline"
                  >
                    Back to login
                  </Link>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
