"use client";

import { Download, Megaphone } from "lucide-react";

import { useAnnouncements } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function ParentAnnouncementsPage() {
  const { data, isLoading, isError, refetch } = useAnnouncements();

  return (
    <>
      <PageHeader
        title="Announcements"
        description="Newsletters and notices from the school."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      ) : data && data.length > 0 ? (
        <div className="space-y-4">
          {data.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <CardDescription>
                  {item.author ? `${item.author} · ` : ""}
                  {new Date(item.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="whitespace-pre-line text-sm text-muted-foreground">
                  {item.content}
                </p>
                {item.document_url && (
                  <div className="flex items-center">
                    <Button
                      asChild
                      size="sm"
                      variant="outline"
                    >
                      <a href={item.document_url} target="_blank" rel="noopener noreferrer">
                        <Download className="h-4 w-4 mr-2" />
                        Download Newsletter
                      </a>
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Megaphone}
          title="No announcements yet"
          description="School announcements and newsletters will appear here."
        />
      )}
    </>
  );
}
