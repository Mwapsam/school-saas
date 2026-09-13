"use client";

import { useState } from "react";
import { Plus, Search, BookOpen } from "lucide-react";
import { toast } from "sonner";

import {
  useLibrarianBooks,
  useLibrarianLibraries,
  useLibrarianCategories,
  useLibrarianCreateBook,
} from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const BOOK_TYPES = [
  { value: "TEXTBOOK", label: "Textbook" },
  { value: "STORYBOOK", label: "Storybook" },
  { value: "TEACHER_RESOURCE", label: "Teacher Resource" },
  { value: "REFERENCE", label: "Reference" },
  { value: "OTHER", label: "Other" },
];
const SCHOOL_LEVELS = [
  { value: "ALL", label: "All levels" },
  { value: "LOWER_SCHOOL", label: "Lower School" },
  { value: "UPPER_SCHOOL", label: "Upper School" },
];

const EMPTY_FORM = {
  library_id: "",
  title: "",
  author: "",
  isbn: "",
  book_number: "",
  category_id: "",
  total_copies: "1",
  price: "",
  book_type: "OTHER",
  school_level: "ALL",
};

export default function LibrarianBooksPage() {
  const [libraryId, setLibraryId] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const { data: libraries, isLoading: librariesLoading } =
    useLibrarianLibraries();
  const { data: categories } = useLibrarianCategories();
  const { data: books, isLoading, isError, refetch } = useLibrarianBooks(
    libraryId || undefined,
    query || undefined
  );
  const createBook = useLibrarianCreateBook();

  const availableLibraries = libraries ?? [];
  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  const openDialog = () => {
    setForm({
      ...EMPTY_FORM,
      library_id: libraryId || availableLibraries[0]?.id || "",
    });
    setDialogOpen(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      !form.library_id ||
      !form.title.trim() ||
      !form.author.trim() ||
      !form.category_id
    )
      return;
    try {
      await createBook.mutateAsync({
        library_id: form.library_id,
        title: form.title.trim(),
        author: form.author.trim() || undefined,
        isbn: form.isbn.trim() || undefined,
        book_number: form.book_number.trim() || undefined,
        category_id: form.category_id || undefined,
        total_copies: Number(form.total_copies) || 1,
        price: form.price.trim() || undefined,
        book_type: form.book_type,
        school_level: form.school_level,
      });
      toast.success(`"${form.title.trim()}" added to the catalog.`);
      setDialogOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add book.");
    }
  };

  return (
    <>
      <PageHeader
        title="Book Catalog"
        description="Search and manage books in your libraries."
        actions={
          <Button size="sm" onClick={openDialog} disabled={librariesLoading}>
            <Plus className="h-4 w-4" />
            Add Book
          </Button>
        }
      />

      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by title, author, ISBN..."
              className="pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
        <Select value={libraryId} onValueChange={setLibraryId}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="All libraries" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All libraries</SelectItem>
            {availableLibraries.map((lib) => (
              <SelectItem key={lib.id} value={lib.id}>
                {lib.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Books</CardTitle>
            <CardDescription>{books?.length ?? 0} books found</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading || librariesLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
            ) : books && books.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="p-3 text-left font-medium">Title</th>
                      <th className="p-3 text-left font-medium">Author</th>
                      <th className="p-3 text-left font-medium">ISBN</th>
                      <th className="p-3 text-right font-medium">Available</th>
                      <th className="p-3 text-right font-medium">Total</th>
                      <th className="p-3 text-center font-medium">Library</th>
                    </tr>
                  </thead>
                  <tbody>
                    {books.map((book) => (
                      <tr key={book.id} className="border-b hover:bg-muted/50">
                        <td className="p-3">
                          <div className="font-medium">{book.title}</div>
                          {book.category_name && (
                            <div className="text-xs text-muted-foreground">
                              {book.category_name}
                            </div>
                          )}
                        </td>
                        <td className="p-3 text-muted-foreground">
                          {book.author || "—"}
                        </td>
                        <td className="p-3 text-muted-foreground">
                          {book.isbn || "—"}
                        </td>
                        <td className="p-3 text-right">
                          <span className="font-semibold">
                            {book.available_copies}
                          </span>
                        </td>
                        <td className="p-3 text-right">{book.total_copies}</td>
                        <td className="p-3 text-center text-sm text-muted-foreground">
                          {book.library_name}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={BookOpen}
                title="No books found"
                description="Start by adding books to your library or try a different search."
              />
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Book</DialogTitle>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label>Library</Label>
              <Select value={form.library_id} onValueChange={set("library_id")}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a library" />
                </SelectTrigger>
                <SelectContent>
                  {availableLibraries.map((lib) => (
                    <SelectItem key={lib.id} value={lib.id}>
                      {lib.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Title</Label>
              <Input
                value={form.title}
                onChange={(e) => set("title")(e.target.value)}
                autoFocus
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Author</Label>
                <Input
                  value={form.author}
                  onChange={(e) => set("author")(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label>ISBN</Label>
                <Input
                  value={form.isbn}
                  onChange={(e) => set("isbn")(e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Book number</Label>
                <Input
                  value={form.book_number}
                  onChange={(e) => set("book_number")(e.target.value)}
                  placeholder="Auto if blank"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Copies</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.total_copies}
                  onChange={(e) => set("total_copies")(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Category</Label>
              <Select
                value={form.category_id}
                onValueChange={set("category_id")}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {(categories ?? []).map((cat) => (
                    <SelectItem key={cat.id} value={cat.id}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select value={form.book_type} onValueChange={set("book_type")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {BOOK_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>School level</Label>
                <Select
                  value={form.school_level}
                  onValueChange={set("school_level")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SCHOOL_LEVELS.map((l) => (
                      <SelectItem key={l.value} value={l.value}>
                        {l.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Price (optional)</Label>
              <Input
                value={form.price}
                onChange={(e) => set("price")(e.target.value)}
                inputMode="decimal"
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  !form.library_id ||
                  !form.title.trim() ||
                  !form.author.trim() ||
                  !form.category_id ||
                  createBook.isPending
                }
              >
                {createBook.isPending ? "Adding…" : "Add Book"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
