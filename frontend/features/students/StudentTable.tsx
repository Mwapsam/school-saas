/**
 * Student table component with sorting, filtering, pagination.
 *
 * Displays list of students with:
 * - Column sorting (click header)
 * - Pagination (prev/next)
 * - Search filtering
 * - Batch filtering
 * - Actions (view, edit, delete)
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
} from '@mui/material';
import { Edit as EditIcon, Delete as DeleteIcon, Visibility as ViewIcon } from '@mui/icons-material';
import { Student } from './hooks';

export interface StudentTableProps {
  students: Student[] | undefined;
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

export function StudentTable({
  students,
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
}: StudentTableProps) {
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
      {/* Search Bar */}
      <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
        <TextField
          label="Search by name or admission number"
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          size="small"
          sx={{ flex: 1 }}
        />
        <Button variant="contained" onClick={handleSearch}>
          Search
        </Button>
      </Box>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
            <TableRow>
              <TableCell
                sx={{ cursor: 'pointer', fontWeight: 600 }}
                onClick={() => handleTableSort('admission_number')}
              >
                Admission #
              </TableCell>
              <TableCell
                sx={{ cursor: 'pointer', fontWeight: 600 }}
                onClick={() => handleTableSort('full_name')}
              >
                Name
              </TableCell>
              <TableCell
                sx={{ cursor: 'pointer', fontWeight: 600 }}
                onClick={() => handleTableSort('date_of_birth')}
              >
                DOB
              </TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Batch</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : students && students.length > 0 ? (
              students.map((student) => (
                <TableRow key={student.id} hover>
                  <TableCell>{student.admission_number}</TableCell>
                  <TableCell>{student.full_name}</TableCell>
                  <TableCell>{student.date_of_birth}</TableCell>
                  <TableCell>{student.email || '-'}</TableCell>
                  <TableCell>{student.batch_name || '-'}</TableCell>
                  <TableCell>
                    <Box
                      sx={{
                        display: 'inline-block',
                        px: 1,
                        py: 0.5,
                        backgroundColor: student.is_active ? '#e8f5e9' : '#ffebee',
                        color: student.is_active ? '#2e7d32' : '#c62828',
                        borderRadius: 1,
                        fontSize: '0.85rem',
                        fontWeight: 500,
                      }}
                    >
                      {student.is_active ? 'Active' : 'Inactive'}
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Link href={`/dashboard/students/${student.id}`} passHref legacyBehavior>
                      <IconButton size="small" component="a" title="View">
                        <ViewIcon fontSize="small" />
                      </IconButton>
                    </Link>
                    {canEdit && (
                      <Link href={`/dashboard/students/${student.id}/edit`} passHref legacyBehavior>
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
                          if (window.confirm(`Delete ${student.full_name}?`)) {
                            onDelete?.(student.id);
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
                <TableCell colSpan={7} align="center" sx={{ py: 3 }}>
                  No students found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      <TablePagination
        rowsPerPageOptions={[10, 25, 50]}
        component="div"
        count={total}
        rowsPerPage={pageSize}
        page={page - 1} // MUI uses 0-indexed pages
        onPageChange={(_, newPage) => onPageChange(newPage + 1)}
        onRowsPerPageChange={(e) => onPageSizeChange(parseInt(e.target.value, 10))}
      />
    </Box>
  );
}
