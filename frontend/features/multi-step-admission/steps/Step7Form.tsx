'use client';

import { useState } from 'react';
import { Box, Grid, Button, CircularProgress, Alert, List, ListItem, ListItemText, Card, CardContent, Typography, LinearProgress } from '@mui/material';
import { CloudUpload as UploadIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useGetRequiredDocuments, useGetDocuments, useUploadDocument } from '../hooks';

interface Step7FormProps {
  applicationId: string;
  onNext?: () => void;
  isLoading?: boolean;
}

export function Step7Form({ applicationId, onNext, isLoading }: Step7FormProps) {
  const [uploadError, setUploadError] = useState<string | null>(null);
  const { data: requiredDocsData } = useGetRequiredDocuments();
  const { data: documentsData, refetch } = useGetDocuments(applicationId);
  const uploadMutation = useUploadDocument(applicationId);

  const uploadedDocTypes = new Set(documentsData?.results.map((d) => d.document_type) || []);
  const allDocTypes = new Set(
    requiredDocsData?.map((d) => d.type) || []
  );
  const allUploaded = Array.from(allDocTypes).every((type) => uploadedDocTypes.has(type));

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
                    {uploadedDocTypes.size} of {allDocTypes.size} documents uploaded
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={(uploadedDocTypes.size / allDocTypes.size) * 100}
                />
              </Box>
              <Typography variant="caption" color="textSecondary">
                All documents are optional but recommended
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>Available Documents</Typography>
          <List>
            {requiredDocsData?.map((doc) => {
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
            disabled={isLoading}
            onClick={onNext}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Proceeding...' : 'Continue to Step 8 (Declaration)'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
