/**
 * Invoice table component — sortable, searchable, paginated.
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  TablePagination,
  IconButton,
  Chip,
} from '@mui/material';
import { Edit as EditIcon, Delete as DeleteIcon, Visibility as ViewIcon } from '@mui/icons-material';
import { Invoice } from './hooks';

export interface InvoiceTableProps {
  invoices: Invoice[] | undefined;
  loading: boolean;
  error: Error | null;
  total: number;
  page: number;
  pageSize: number;
  search: string;
  ordering: string;

  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onSearchChange: (search: string) => void;
  onOrderingChange: (ordering: string) => void;
  onDelete?: (id: string) => void;

  canEdit?: boolean;
  canDelete?: boolean;
}

const statusColors: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
  draft: 'default',
  sent: 'info',
  paid: 'success',
  overdue: 'error',
};

export function InvoiceTable({
  invoices,
  loading,
  error,
  total,
  page,
  pageSize,
  search,
  ordering,
  onPageChange,
  onPageSizeChange,
  onSearchChange,
  onOrderingChange,
  onDelete,
  canEdit = true,
  canDelete = true,
}: InvoiceTableProps) {
  const [localSearch, setLocalSearch] = useState(search);

  const handleSearch = () => {
    onSearchChange(localSearch);
  };

  const handleTableSort = (field: string) => {
    const newOrdering = ordering === field ? `-${field}` : field;
    onOrderingChange(newOrdering);
  };

  if (error) {
    return <Alert severity="error">{error.message}</Alert>;
  }

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
        <TextField
          label="Search by student name or invoice number"
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          size="small"
          sx={{ flex: 1 }}
        />
        <Button variant="contained" onClick={handleSearch}>
          Search
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
            <TableRow>
              <TableCell sx={{ cursor: 'pointer', fontWeight: 600 }} onClick={() => handleTableSort('invoice_number')}>
                Invoice #
              </TableCell>
              <TableCell sx={{ cursor: 'pointer', fontWeight: 600 }} onClick={() => handleTableSort('student_name')}>
                Student
              </TableCell>
              <TableCell sx={{ cursor: 'pointer', fontWeight: 600 }} onClick={() => handleTableSort('amount')}>
                Amount
              </TableCell>
              <TableCell sx={{ cursor: 'pointer', fontWeight: 600 }} onClick={() => handleTableSort('due_date')}>
                Due Date
              </TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : invoices && invoices.length > 0 ? (
              invoices.map((invoice) => (
                <TableRow key={invoice.id} hover>
                  <TableCell>{invoice.invoice_number}</TableCell>
                  <TableCell>{invoice.student_name}</TableCell>
                  <TableCell>${invoice.amount.toFixed(2)}</TableCell>
                  <TableCell>{invoice.due_date}</TableCell>
                  <TableCell>
                    <Chip label={invoice.status} color={statusColors[invoice.status]} size="small" />
                  </TableCell>
                  <TableCell align="right">
                    <Link href={`/dashboard/invoices/${invoice.id}`} passHref legacyBehavior>
                      <IconButton size="small" component="a" title="View">
                        <ViewIcon fontSize="small" />
                      </IconButton>
                    </Link>
                    {canEdit && (
                      <Link href={`/dashboard/invoices/${invoice.id}/edit`} passHref legacyBehavior>
                        <IconButton size="small" component="a" title="Edit">
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Link>
                    )}
                    {canDelete && (
                      <IconButton
                        size="small"
                        title="Delete"
                        onClick={() => {
                          if (window.confirm(`Delete invoice ${invoice.invoice_number}?`)) {
                            onDelete?.(invoice.id);
                          }
                        }}
                      >
                        <DeleteIcon fontSize="small" color="error" />
                      </IconButton>
                    )}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                  No invoices found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        rowsPerPageOptions={[10, 25, 50]}
        component="div"
        count={total}
        rowsPerPage={pageSize}
        page={page - 1}
        onPageChange={(_, newPage) => onPageChange(newPage + 1)}
        onRowsPerPageChange={(e) => onPageSizeChange(parseInt(e.target.value, 10))}
      />
    </Box>
  );
}
