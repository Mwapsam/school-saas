'use client';

import React, { useState } from 'react';
import {
  Container,
  TextField,
  Button,
  Card,
  CardContent,
  Stack,
  Typography,
  Alert,
  Box,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';

import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard } from '@/components/page/SectionCard';
import { StatusBadge } from '@/components/data/StatusBadge';
import { LoadingState } from '@/components/feedback/LoadingState';

import { useAdmissionStatusCheck } from '@/features/admission-management/hooks';

const AdmissionStatusCheckPage: React.FC = () => {
  const [applicationNumber, setApplicationNumber] = useState('');
  const [searchSubmitted, setSearchSubmitted] = useState(false);

  // Query - only enabled after search submission
  const { data: result, isLoading, error } = useAdmissionStatusCheck(
    searchSubmitted ? applicationNumber : '',
    { enabled: searchSubmitted && !!applicationNumber }
  );

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (applicationNumber.trim()) {
      setSearchSubmitted(true);
    }
  };

  const handleClear = () => {
    setApplicationNumber('');
    setSearchSubmitted(false);
  };

  return (
    <Page>
      <PageHeader
        title="Check Application Status"
        description="Enter your application number to check the status"
      />

      <PageContent>
        <Container maxWidth="sm">
          {/* Search Form */}
          <SectionCard title="Application Status Lookup">
            <form onSubmit={handleSearch}>
              <Stack spacing={2}>
                <TextField
                  label="Application Number"
                  value={applicationNumber}
                  onChange={(e) => setApplicationNumber(e.target.value.toUpperCase())}
                  placeholder="e.g., APP2024001"
                  fullWidth
                  disabled={isLoading}
                />

                <Stack direction="row" spacing={2}>
                  <Button
                    type="submit"
                    variant="contained"
                    fullWidth
                    startIcon={<SearchIcon />}
                    disabled={!applicationNumber.trim() || isLoading}
                  >
                    {isLoading ? 'Searching...' : 'Check Status'}
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={handleClear}
                    disabled={isLoading}
                  >
                    Clear
                  </Button>
                </Stack>
              </Stack>
            </form>
          </SectionCard>

          {/* Loading State */}
          {isLoading && <LoadingState />}

          {/* Error State */}
          {error && searchSubmitted && !isLoading && (
            <Alert severity="error" sx={{ mt: 3 }}>
              Application not found. Please check the application number and try again.
            </Alert>
          )}

          {/* Results */}
          {result && searchSubmitted && !isLoading && (
            <Card sx={{ mt: 3 }}>
              <CardContent>
                <Stack spacing={2}>
                  <Box>
                    <Typography variant="caption" color="textSecondary">
                      Application Number
                    </Typography>
                    <Typography variant="h6">
                      {result.application_number}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="textSecondary">
                      Applicant Name
                    </Typography>
                    <Typography variant="h6">
                      {result.applicant_name}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="textSecondary">
                      Current Status
                    </Typography>
                    <Box sx={{ mt: 1 }}>
                      <StatusBadge status={result.status} />
                    </Box>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="textSecondary">
                      Application Date
                    </Typography>
                    <Typography>
                      {new Date(result.application_date).toLocaleDateString()}
                    </Typography>
                  </Box>

                  {result.remarks && (
                    <Box>
                      <Typography variant="caption" color="textSecondary">
                        Remarks
                      </Typography>
                      <Typography sx={{ mt: 0.5 }}>
                        {result.remarks}
                      </Typography>
                    </Box>
                  )}

                  {/* Status-specific messages */}
                  {result.status === 'approved' && (
                    <Alert severity="success">
                      Congratulations! Your application has been approved. You will be
                      contacted soon with admission details.
                    </Alert>
                  )}

                  {result.status === 'admitted' && (
                    <Alert severity="success">
                      Welcome! You have been successfully admitted. Please log in to the
                      parent portal for further details.
                    </Alert>
                  )}

                  {result.status === 'rejected' && (
                    <Alert severity="error">
                      Unfortunately, your application was not successful at this time.
                      {result.remarks && ` Reason: ${result.remarks}`}
                    </Alert>
                  )}

                  {result.status === 'under_review' && (
                    <Alert severity="info">
                      Your application is currently under review. We will notify you of
                      the outcome shortly.
                    </Alert>
                  )}

                  {result.status === 'submitted' && (
                    <Alert severity="info">
                      Your application has been received and is awaiting review.
                    </Alert>
                  )}
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Help Text */}
          {!searchSubmitted && (
            <Alert severity="info" sx={{ mt: 3 }}>
              Enter your application number (provided when you submitted your application)
              to check the current status of your admission application.
            </Alert>
          )}
        </Container>
      </PageContent>
    </Page>
  );
};

export default AdmissionStatusCheckPage;
