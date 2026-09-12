'use client';

import { useState, useEffect } from 'react';
import { DataGrid, type GridColDef, type GridSortModel, type GridColumnVisibilityModel } from '@mui/x-data-grid';
import { Box, TextField, Alert, Button, InputAdornment, useMediaQuery, useTheme } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { colors } from '@/design-system/tokens';

export interface DataTableProps<T extends { id: string }> {
  rows: T[];
  columns: GridColDef<T>[];
  rowCount: number;
  loading: boolean;
  error?: Error | null;
  onRetry?: () => void;

  paginationModel: { page: number; pageSize: number };
  onPaginationModelChange: (model: { page: number; pageSize: number }) => void;

  sortModel?: GridSortModel;
  onSortModelChange?: (model: GridSortModel) => void;

  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;

  toolbarActions?: React.ReactNode;
  emptyMessage?: string;
  height?: number;

  checkboxSelection?: boolean;
  onSelectionChange?: (selectedIds: (string | number)[]) => void;

  /** Column field names to hide on mobile (sm and below) */
  hideOnMobile?: string[];
}

/**
 * Shared server-paginated data table used across every domain list page.
 * Wraps MUI X DataGrid with search, server pagination/sort, and consistent
 * loading/empty/error states so no domain hand-rolls its own table chrome.
 */
export function DataTable<T extends { id: string }>({
  rows,
  columns,
  rowCount,
  loading,
  error,
  onRetry,
  paginationModel,
  onPaginationModelChange,
  sortModel,
  onSortModelChange,
  search,
  onSearchChange,
  searchPlaceholder = 'Search...',
  toolbarActions,
  emptyMessage = 'No records found',
  height = 520,
  checkboxSelection = false,
  onSelectionChange,
  hideOnMobile = [],
}: DataTableProps<T>) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  // Debounce search input so we don't refetch on every keystroke.
  const [localSearch, setLocalSearch] = useState(search);
  const [selectedRows, setSelectedRows] = useState<(string | number)[]>([]);

  // Build column visibility model based on breakpoint
  const columnVisibilityModel: GridColumnVisibilityModel = {};
  if (isMobile) {
    hideOnMobile.forEach((field) => {
      columnVisibilityModel[field] = false;
    });
  }

  useEffect(() => setLocalSearch(search), [search]);

  useEffect(() => {
    const handle = setTimeout(() => {
      if (localSearch !== search) onSearchChange(localSearch);
    }, 400);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localSearch]);

  if (error) {
    return (
      <Alert
        severity="error"
        action={
          onRetry && (
            <Button color="inherit" size="small" onClick={onRetry}>
              Retry
            </Button>
          )
        }
      >
        {error.message || 'Failed to load data'}
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder={searchPlaceholder}
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          sx={{ minWidth: 240, flex: '1 1 auto', maxWidth: 400 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        {toolbarActions && <Box sx={{ ml: 'auto' }}>{toolbarActions}</Box>}
      </Box>

      <Box sx={{ width: '100%', minWidth: 0, height, bgcolor: 'background.paper', overflowX: 'auto' }}>
        <DataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          rowCount={rowCount}
          paginationMode="server"
          sortingMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={onPaginationModelChange}
          sortModel={sortModel}
          onSortModelChange={onSortModelChange}
          pageSizeOptions={[10, 25, 50]}
          disableColumnMenu
          disableRowSelectionOnClick={!checkboxSelection}
          checkboxSelection={checkboxSelection}
          rowSelectionModel={selectedRows}
          onRowSelectionModelChange={(newSelection) => {
            setSelectedRows(newSelection);
            onSelectionChange?.(newSelection);
          }}
          columnVisibilityModel={columnVisibilityModel}
          localeText={{ noRowsLabel: emptyMessage }}
          sx={{
            border: 'none',
            '& .MuiDataGrid-columnHeaders': { bgcolor: colors.gray[100] },
          }}
        />
      </Box>
    </Box>
  );
}
