"use client";

import { useState } from "react";
import { Plus, Tag } from "lucide-react";
import { toast } from "sonner";

import {
  useLibrarianCategories,
  useLibrarianCreateCategory,
} from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function CategoriesPage() {
  const [showForm, setShowForm] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");

  const { data: categories, isLoading, isError, refetch } =
    useLibrarianCategories();
  const createCategory = useLibrarianCreateCategory();

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newCategoryName.trim();
    if (!name) return;

    try {
      await createCategory.mutateAsync(name);
      toast.success(`Category "${name}" added.`);
      setNewCategoryName("");
      setShowForm(false);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Could not add category.",
      );
    }
  };

  return (
    <>
      <PageHeader
        title="Book Categories"
        description="Manage book categories for your libraries."
        actions={
          !showForm && (
            <Button size="sm" onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4" />
              Add Category
            </Button>
          )
        }
      />

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">New Category</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddCategory} className="flex gap-2">
              <Input
                placeholder="Category name"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                autoFocus
              />
              <Button
                type="submit"
                disabled={!newCategoryName.trim() || createCategory.isPending}
              >
                {createCategory.isPending ? "Adding…" : "Add"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowForm(false);
                  setNewCategoryName("");
                }}
              >
                Cancel
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Categories</CardTitle>
            <CardDescription>
              {categories?.length ?? 0} categories available
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </div>
            ) : categories && categories.length > 0 ? (
              <ul className="divide-y rounded-lg border">
                {categories.map((category) => (
                  <li
                    key={category.id}
                    className="flex items-center justify-between p-4"
                  >
                    <div className="flex items-center gap-3">
                      <Tag className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{category.name}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={Tag}
                title="No categories"
                description="Start by adding a category for organizing your books."
              />
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
