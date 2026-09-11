/**
 * Library books list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useLibraryBookList } from '@/features/library/hooks';

export default function BooksPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data, error } = useLibraryBookList({ page: 1, page_size: 10 });

  if (!bootstrap || !isModuleEnabled('library') || !can('library.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view library books.</Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Library Books
        </Typography>

        {error && <Alert severity="error">{error.message}</Alert>}

        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Author</TableCell>
                <TableCell>ISBN</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Available</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.results?.map((book) => (
                <TableRow key={book.id} hover>
                  <TableCell>{book.title}</TableCell>
                  <TableCell>{book.author}</TableCell>
                  <TableCell>{book.isbn}</TableCell>
                  <TableCell>{book.category_name}</TableCell>
                  <TableCell>{book.available_copies} / {book.total_copies}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Container>
  );
}
