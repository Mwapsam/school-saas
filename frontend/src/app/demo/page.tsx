"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Users,
  BarChart3,
  Shield,
  Zap,
  Clock,
  Award,
} from "lucide-react";
import { toast } from "sonner";

interface FormData {
  full_name: string;
  email: string;
  phone: string;
  school_name: string;
  message: string;
}

export default function DemoPage() {
  const [formData, setFormData] = React.useState<FormData>({
    full_name: "",
    email: "",
    phone: "",
    school_name: "",
    message: "",
  });

  const [isLoading, setIsLoading] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await fetch("/api/v1/demo-requests/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error("Failed to submit demo request");
      }

      setSubmitted(true);
      toast.success("Demo request submitted successfully!");

      // Reset form
      setFormData({
        full_name: "",
        email: "",
        phone: "",
        school_name: "",
        message: "",
      });

      // Scroll to success message
      setTimeout(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }, 100);
    } catch (error) {
      console.error("Error submitting demo request:", error);
      toast.error("Failed to submit demo request. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  // Reset success message after 5 seconds
  React.useEffect(() => {
    if (submitted) {
      const timer = setTimeout(() => setSubmitted(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [submitted]);

  const features = [
    {
      icon: <Users className="h-6 w-6 text-blue-600" />,
      title: "Multi-Tenant Support",
      description:
        "Manage multiple schools from a single platform with complete data isolation",
    },
    {
      icon: <BarChart3 className="h-6 w-6 text-green-600" />,
      title: "Analytics & Reports",
      description:
        "Comprehensive insights into academic performance, finances, and operations",
    },
    {
      icon: <Shield className="h-6 w-6 text-red-600" />,
      title: "Enterprise Security",
      description:
        "Bank-level encryption, role-based access control, and audit logs",
    },
    {
      icon: <Zap className="h-6 w-6 text-yellow-600" />,
      title: "Easy Integration",
      description:
        "Seamless integration with existing systems and third-party tools",
    },
    {
      icon: <Clock className="h-6 w-6 text-purple-600" />,
      title: "Real-Time Updates",
      description:
        "Instant notifications and live data synchronization across all users",
    },
    {
      icon: <Award className="h-6 w-6 text-pink-600" />,
      title: "Industry Best Practices",
      description:
        "Built by education experts with years of school management experience",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Navigation */}
      <nav className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="text-xl font-bold text-slate-900">
              School Management Platform
            </div>
            <Link href="/login">
              <Button variant="outline">Login</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-slate-900 sm:text-5xl">
            Modern School Management
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-xl text-slate-600">
            Streamline operations, improve efficiency, and enhance the learning
            experience with our comprehensive school management platform.
          </p>
        </div>
      </section>

      {/* Features Section */}
      <section className="bg-white py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 className="mb-12 text-center text-3xl font-bold text-slate-900">
            Why Choose Our Platform?
          </h2>
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, idx) => (
              <Card key={idx} className="p-6">
                <div className="mb-4 rounded-lg bg-slate-100 p-3 w-fit">
                  {feature.icon}
                </div>
                <h3 className="mb-2 text-lg font-semibold text-slate-900">
                  {feature.title}
                </h3>
                <p className="text-slate-600">{feature.description}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Demo Request Section */}
      <section className="py-16">
        <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8">
          {submitted && (
            <Card className="mb-8 border-green-200 bg-green-50 p-6">
              <h3 className="mb-2 text-lg font-semibold text-green-900">
                Demo Request Submitted!
              </h3>
              <p className="text-green-800">
                Thank you for your interest. Our team will contact you shortly
                to schedule a demo.
              </p>
            </Card>
          )}

          <Card className="p-8">
            <h2 className="mb-2 text-3xl font-bold text-slate-900">
              Book a Demo
            </h2>
            <p className="mb-8 text-slate-600">
              See how our platform can transform your school management.
              Fill out the form below and our team will be in touch.
            </p>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label htmlFor="full_name">Full Name</Label>
                  <Input
                    id="full_name"
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="Your name"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="your@email.com"
                    required
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                    placeholder="+254 712 345 678"
                  />
                </div>
                <div>
                  <Label htmlFor="school_name">School/Organization Name</Label>
                  <Input
                    id="school_name"
                    name="school_name"
                    value={formData.school_name}
                    onChange={handleChange}
                    placeholder="Your school name"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="message">Message</Label>
                <Textarea
                  id="message"
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                  placeholder="Tell us about your school and what you're looking for..."
                  rows={4}
                />
              </div>

              <div className="text-sm text-slate-600">
                We typically respond within 24 hours. You can also reach us at
                support@schoolmanagement.com
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full"
                size="lg"
              >
                {isLoading ? "Submitting..." : "Request Demo"}
              </Button>
            </form>
          </Card>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="bg-white py-16">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <h2 className="mb-12 text-center text-3xl font-bold text-slate-900">
            Frequently Asked Questions
          </h2>
          <div className="space-y-6">
            {[
              {
                q: "How long does the implementation take?",
                a: "Most implementations are completed within 2-4 weeks, depending on your school size and requirements.",
              },
              {
                q: "Is training provided?",
                a: "Yes, we provide comprehensive training for your staff and ongoing support.",
              },
              {
                q: "Can I integrate with my existing systems?",
                a: "Our platform supports integrations with most common educational and business systems.",
              },
              {
                q: "What about data security?",
                a: "We follow industry best practices with encryption, regular backups, and compliance with international standards.",
              },
            ].map((faq, idx) => (
              <Card key={idx} className="p-6">
                <h3 className="mb-2 text-lg font-semibold text-slate-900">
                  {faq.q}
                </h3>
                <p className="text-slate-600">{faq.a}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center text-slate-600">
            <p>
              &copy; 2026 School Management Platform. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
