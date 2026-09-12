'use client';

import { useState, useMemo } from 'react';

export interface ServerTableState {
  page: number; // 1-indexed, matches DRF pagination
  pageSize: number;
  search: string;
  ordering: string; // DRF-style ordering, e.g. "-created_at"
}

export interface UseServerTableOptions {
  initialPageSize?: number;
  initialOrdering?: string;
}

/**
 * Encapsulates page/pageSize/search/sort state for a server-paginated table
 * and exposes DRF-compatible query params, plus MUI DataGrid-compatible
 * models for wiring directly into <DataTable />.
 */
export function useServerTable(options: UseServerTableOptions = {}) {
  const { initialPageSize = 10, initialOrdering = '' } = options;

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState(initialOrdering);

  const queryParams = useMemo(
    () => ({
      page,
      page_size: pageSize,
      ...(search ? { search } : {}),
      ...(ordering ? { ordering } : {}),
    }),
    [page, pageSize, search, ordering]
  );

  const paginationModel = useMemo(
    () => ({ page: page - 1, pageSize }), // MUI DataGrid is 0-indexed
    [page, pageSize]
  );

  function onPaginationModelChange(model: { page: number; pageSize: number }) {
    setPage(model.page + 1);
    setPageSize(model.pageSize);
  }

  function onSortModelChange(model: Array<{ field: string; sort: 'asc' | 'desc' | null }>) {
    const [first] = model;
    if (!first || !first.sort) {
      setOrdering(initialOrdering);
      return;
    }
    setOrdering(first.sort === 'desc' ? `-${first.field}` : first.field);
    setPage(1);
  }

  function onSearchChange(value: string) {
    setSearch(value);
    setPage(1);
  }

  return {
    page,
    pageSize,
    search,
    ordering,
    queryParams,
    paginationModel,
    onPaginationModelChange,
    onSortModelChange,
    onSearchChange,
  };
}
