'use client';

import { useState } from 'react';
import { Box, Grid, Button, CircularProgress, Alert, List, ListItem, ListItemText, Card, CardContent, Typography, LinearProgress } from '@mui/material';
import { CloudUpload as UploadIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useGetRequiredDocuments, useGetDocuments, useUploadDocument } from '../hooks';

interface Step6FormProps {
  applicationId: string;
  onNext?: () => void;
  isLoading?: boolean;
}

export function Step6Form({ applicationId, onNext, isLoading }: Step6FormProps) {
  const [uploadError, setUploadError] = useState<string | null>(null);
  const { data: requiredDocsData } = useGetRequiredDocuments();
  const { data: documentsData, refetch } = useGetDocuments(applicationId);
  const uploadMutation = useUploadDocument(applicationId);

  const uploadedDocTypes = new Set(documentsData?.results.map((d) => d.document_type) || []);
  const requiredDocTypes = new Set(
    requiredDocsData?.filter((d) => d.required).map((d) => d.type) || []
  );
  const allRequiredUploaded = Array.from(requiredDocTypes).every((type) => uploadedDocTypes.has(type));

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, docType: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', docType);

    try {
      await uploadMutation.mutateAsync(formData);
      await refetch();
    } catch (error: any) {
      setUploadError(error?.message || 'Failed to upload document');
    }
  };

  return (
    <Box>
      {uploadError && <Alert severity="error" sx={{ mb: 2 }}>{uploadError}</Alert>}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Document Upload Progress
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">
                    {uploadedDocTypes.size} of {requiredDocTypes.size} required documents uploaded
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(uploadedDocTypes.size / requiredDocTypes.size) * 100}
                />
              </Box>
              <Typography variant="caption" color="textSecondary">
                * Required documents must be uploaded to proceed
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6">Required Documents *</Typography>
          <List>
            {requiredDocsData
              ?.filter((d) => d.required)
              .map((doc) => {
                const uploaded = documentsData?.results.find((d) => d.document_type === doc.type);
                return (
                  <ListItem
                    key={doc.type}
                    secondaryAction={
                      uploaded ? (
                        <Typography variant="caption" color="success.main">
                          ✓ Uploaded
                        </Typography>
                      ) : (
                        <Button
                          component="label"
                          size="small"
                          startIcon={<UploadIcon />}
                          disabled={uploadMutation.isPending}
                        >
                          Upload
                          <input
                            hidden
                            type="file"
                            onChange={(e) => handleFileUpload(e, doc.type)}
                            accept=".pdf,.jpg,.jpeg,.png"
                          />
                        </Button>
                      )
                    }
                  >
                    <ListItemText
                      primary={doc.display_name}
                      secondary={
                        uploaded
                          ? `${uploaded.original_filename} (${uploaded.file_size_mb}MB)`
                          : 'Not uploaded'
                      }
                    />
                  </ListItem>
                );
              })}
          </List>
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6">Optional Documents</Typography>
          <List>
            {requiredDocsData
              ?.filter((d) => !d.required)
              .map((doc) => {
                const uploaded = documentsData?.results.find((d) => d.document_type === doc.type);
                return (
                  <ListItem
                    key={doc.type}
                    secondaryAction={
                      uploaded ? (
                        <Typography variant="caption" color="success.main">
                          ✓ Uploaded
                        </Typography>
                      ) : (
                        <Button
                          component="label"
                          size="small"
                          startIcon={<UploadIcon />}
                          disabled={uploadMutation.isPending}
                        >
                          Upload
                          <input
                            hidden
                            type="file"
                            onChange={(e) => handleFileUpload(e, doc.type)}
                            accept=".pdf,.jpg,.jpeg,.png"
                          />
                        </Button>
                      )
                    }
                  >
                    <ListItemText
                      primary={doc.display_name}
                      secondary={
                        uploaded
                          ? `${uploaded.original_filename} (${uploaded.file_size_mb}MB)`
                          : 'Not uploaded'
                      }
                    />
                  </ListItem>
                );
              })}
          </List>
        </Grid>

        <Grid item xs={12}>
          <Button
            variant="contained"
            disabled={!allRequiredUploaded || isLoading}
            onClick={onNext}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Proceeding...' : 'Continue to Step 7 (Review & Submit)'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
