import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Switch,
  TextField,
  Typography,
  Alert,
  AlertTitle,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import ArticleIcon from '@mui/icons-material/Article';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import SettingsIcon from '@mui/icons-material/Settings';
import WarningIcon from '@mui/icons-material/Warning';

import { ingestAPI } from '../services/api';

// 支持的文件类型
const SUPPORTED_FILE_TYPES = [
  '.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx', 
  '.xls', '.xlsx', '.csv', '.md', '.html', '.htm'
];

// 上传状态
const UPLOAD_STATUS = {
  READY: 'ready',
  UPLOADING: 'uploading',
  PROCESSING: 'processing',
  SUCCESS: 'success',
  ERROR: 'error',
};

function Upload({ showNotification }) {
  // 文件状态
  const [files, setFiles] = useState([]);
  const [uploadStatus, setUploadStatus] = useState(UPLOAD_STATUS.READY);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingFile, setProcessingFile] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  // 配置选项
  const [config, setConfig] = useState({
    chunker: 'recursive',
    chunkSize: 1000,
    chunkOverlap: 200,
    metadataExtraction: true,
    languageDetection: true,
    extractImages: false,
    indexName: '', // 可选
  });
  
  // 重复文件检测状态
  const [existingDocuments, setExistingDocuments] = useState([]);
  const [duplicateFileDialog, setDuplicateFileDialog] = useState(false);
  const [duplicateFiles, setDuplicateFiles] = useState([]);
  
  // 加载已有文档列表用于检查重复
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const response = await ingestAPI.getAllDocuments();
        setExistingDocuments(response.documents || []);
      } catch (error) {
        console.error("获取文档列表失败:", error);
        // 如果无法获取文档列表，设置为空数组
        setExistingDocuments([]);
      }
    };
    
    fetchDocuments();
  }, []);

  // 检查文档是否可能重复
  const checkDocumentDuplicates = (file) => {
    // 根据文件名和大小初步判断可能的重复
    const possibleDuplicates = existingDocuments.filter(doc => 
      // 检查文件名相似性
      (doc.name === file.name || 
       (doc.metadata && doc.metadata.title === file.name) ||
       doc.name.toLowerCase() === file.name.toLowerCase()) && 
      // 检查文件大小相似性 (允许100字节的误差)
      Math.abs(doc.file_size - file.size) < 100
    );
    
    return possibleDuplicates;
  };

  // 处理上传文件变更
  const handleFileChange = (event) => {
    if (uploadStatus === UPLOAD_STATUS.UPLOADING || uploadStatus === UPLOAD_STATUS.PROCESSING) {
      return;
    }

    const selectedFiles = Array.from(event.target.files);
    const validFiles = [];
    const invalidFiles = [];
    const duplicatesFound = [];

    selectedFiles.forEach(file => {
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      if (SUPPORTED_FILE_TYPES.includes(fileExtension)) {
        // 检查文件是否重复
        const duplicates = checkDocumentDuplicates(file);
        
        // 记录重复文件信息
        if (duplicates && duplicates.length > 0) {
          duplicatesFound.push({
            file,
            duplicates
          });
        }
        
        validFiles.push({
          file,
          id: Date.now() + Math.random().toString(36).substring(2),
          status: UPLOAD_STATUS.READY,
          progress: 0,
          error: null,
          hasDuplicates: duplicates && duplicates.length > 0,
          duplicates: duplicates || []
        });
      } else {
        invalidFiles.push(file.name);
      }
    });

    if (invalidFiles.length > 0) {
      showNotification(
        `不支持的文件类型: ${invalidFiles.join(', ')}`, 
        'error'
      );
    }
    
    // 显示重复文件提示
    if (duplicatesFound.length > 0) {
      setDuplicateFiles(duplicatesFound);
      setDuplicateFileDialog(true);
    }

    setFiles([...files, ...validFiles]);
    // 重置文件输入框，允许重复选择相同的文件
    event.target.value = null;
  };

  // 关闭重复文件对话框
  const handleCloseDuplicateDialog = () => {
    setDuplicateFileDialog(false);
  };

  // 处理重复文件处理 - 保留所有文件
  const handleKeepAllFiles = () => {
    setDuplicateFileDialog(false);
  };

  // 处理重复文件处理 - 移除重复文件
  const handleRemoveDuplicates = () => {
    // 过滤掉标记为有重复的文件
    const filteredFiles = files.filter(file => !file.hasDuplicates);
    setFiles(filteredFiles);
    setDuplicateFileDialog(false);
  };

  // 删除文件
  const handleDeleteFile = (fileId) => {
    setFiles(files.filter(file => file.id !== fileId));
  };

  // 清除所有文件
  const handleClearFiles = () => {
    setFiles([]);
  };

  // 处理配置变更
  const handleConfigChange = (field, value) => {
    setConfig({
      ...config,
      [field]: value,
    });
  };

  // 上传文件
  const handleUpload = async () => {
    if (files.length === 0) {
      showNotification('请先选择文件', 'warning');
      return;
    }

    setUploadStatus(UPLOAD_STATUS.UPLOADING);
    setUploadProgress(0);
    
    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < files.length; i++) {
      const fileObj = files[i];
      if (fileObj.status === UPLOAD_STATUS.SUCCESS) {
        successCount++;
        continue;
      }

      // 更新当前处理文件
      setProcessingFile(fileObj.file.name);
      setUploadProgress(0);
      
      // 更新文件状态
      const updatedFiles = [...files];
      updatedFiles[i] = { ...fileObj, status: UPLOAD_STATUS.UPLOADING, progress: 0 };
      setFiles(updatedFiles);

      try {
        // 上传文件
        const formData = new FormData();
        formData.append('file', fileObj.file);
        
        // 添加配置选项为metadata
        const configMetadata = {
          chunker: config.chunker,
          chunk_size: config.chunkSize,
          chunk_overlap: config.chunkOverlap,
          extract_metadata: config.metadataExtraction,
          detect_language: config.languageDetection,
          extract_images: config.extractImages
        };
        
        if (config.indexName) {
          configMetadata.index_name = config.indexName;
        }
        
        // 添加元数据
        formData.append('metadata', JSON.stringify(configMetadata));

        const response = await ingestAPI.uploadDocument(
          formData, 
          (progressEvent) => {
            const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
            setUploadProgress(progress);
            
            // 更新文件进度
            const progressFiles = [...files];
            progressFiles[i] = { ...progressFiles[i], progress };
            setFiles(progressFiles);
          }
        );

        // 检查上传响应是否包含错误
        if (response.error) {
          const errorFiles = [...files];
          errorFiles[i] = { 
            ...errorFiles[i], 
            status: UPLOAD_STATUS.ERROR, 
            error: response.error || '上传失败',
          };
          setFiles(errorFiles);
          errorCount++;
          continue;
        }

        // 上传成功后进入处理阶段
        const processingFiles = [...files];
        processingFiles[i] = { 
          ...processingFiles[i], 
          status: UPLOAD_STATUS.PROCESSING, 
          progress: 100,
          documentId: response.document_id, 
        };
        setFiles(processingFiles);
        setUploadStatus(UPLOAD_STATUS.PROCESSING);

        // 检查处理状态
        const maxRetries = 30;
        let retryCount = 0;
        let isProcessed = false;

        while (!isProcessed && retryCount < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 2000)); // 每2秒检查一次
          
          try {
            const status = await ingestAPI.getIngestStatus(response.document_id);
            
            // 检查是否有错误
            if (status.error) {
              isProcessed = true;
              const errorFiles = [...files];
              errorFiles[i] = { 
                ...errorFiles[i], 
                status: UPLOAD_STATUS.ERROR, 
                error: status.error || '处理失败',
              };
              setFiles(errorFiles);
              errorCount++;
              break;
            }
            
            // 更新处理进度
            const statusFiles = [...files];
            const fileIndex = statusFiles.findIndex(f => f.id === fileObj.id);
            if (fileIndex !== -1) {
              statusFiles[fileIndex] = { 
                ...statusFiles[fileIndex], 
                progress: status.progress,
                status: status.status === 'completed' 
                  ? UPLOAD_STATUS.SUCCESS 
                  : status.status === 'failed' 
                    ? UPLOAD_STATUS.ERROR 
                    : UPLOAD_STATUS.PROCESSING,
                error: status.error,
                metadata: status.metadata
              };
              setFiles(statusFiles);
            }
            
            if (status.status === 'completed') {
              isProcessed = true;
              successCount++;
              
              // 将新文档添加到现有文档列表，以便后续检查重复
              setExistingDocuments(prevDocs => [
                ...prevDocs, 
                {
                  document_id: response.document_id,
                  name: fileObj.file.name,
                  file_size: fileObj.file.size,
                  file_type: fileObj.file.name.split('.').pop().toLowerCase(),
                  upload_date: new Date().toISOString(),
                  status: 'completed'
                }
              ]);
            } else if (status.status === 'failed') {
              isProcessed = true;
              errorCount++;
            }
          } catch (error) {
            console.error(`获取文档状态失败: ${error.message}`);
            // 继续重试，不终止循环
          }
          
          retryCount++;
        }

        if (!isProcessed) {
          // 超时
          const timeoutFiles = [...files];
          timeoutFiles[i] = { 
            ...timeoutFiles[i], 
            status: UPLOAD_STATUS.ERROR, 
            error: '处理超时，请检查系统状态',
          };
          setFiles(timeoutFiles);
          errorCount++;
        }
      } catch (error) {
        const errorFiles = [...files];
        errorFiles[i] = { 
          ...errorFiles[i], 
          status: UPLOAD_STATUS.ERROR, 
          error: error.message || '上传失败',
        };
        setFiles(errorFiles);
        errorCount++;
      }
    }

    // 所有文件处理完成
    setUploadStatus(UPLOAD_STATUS.READY);
    setProcessingFile('');

    if (errorCount === 0 && successCount > 0) {
      showNotification(`成功处理 ${successCount} 个文件`, 'success');
    } else if (errorCount > 0 && successCount > 0) {
      showNotification(`${successCount} 个文件成功，${errorCount} 个文件失败`, 'warning');
    } else if (errorCount > 0 && successCount === 0) {
      showNotification(`所有文件处理失败`, 'error');
    }
  };

  // 获取文件状态图标
  const getStatusIcon = (status) => {
    switch (status) {
      case UPLOAD_STATUS.SUCCESS:
        return <CheckCircleIcon color="success" />;
      case UPLOAD_STATUS.ERROR:
        return <ErrorIcon color="error" />;
      case UPLOAD_STATUS.UPLOADING:
      case UPLOAD_STATUS.PROCESSING:
        return <CircularProgress size={20} />;
      default:
        return <ArticleIcon color="primary" />;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          文档上传
        </Typography>
        <Typography variant="body1" paragraph align="center" color="textSecondary">
          上传您的文档以构建知识库，支持多种文档格式
        </Typography>

        <Grid container spacing={3}>
          <Grid item xs={12} md={showAdvanced ? 8 : 12}>
            {/* 文件上传区域 */}
            <Paper 
              sx={{ 
                p: 3, 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center',
                border: '2px dashed',
                borderColor: 'divider',
                backgroundColor: 'background.default'
              }}
            >
              <input
                type="file"
                id="file-input"
                multiple
                onChange={handleFileChange}
                style={{ display: 'none' }}
                disabled={uploadStatus === UPLOAD_STATUS.UPLOADING || uploadStatus === UPLOAD_STATUS.PROCESSING}
              />
              <label htmlFor="file-input">
                <Button
                  variant="contained"
                  component="span"
                  startIcon={<CloudUploadIcon />}
                  disabled={uploadStatus === UPLOAD_STATUS.UPLOADING || uploadStatus === UPLOAD_STATUS.PROCESSING}
                  sx={{ mb: 2 }}
                >
                  选择文件
                </Button>
              </label>
              <Typography variant="body2" color="textSecondary" align="center">
                支持以下格式: {SUPPORTED_FILE_TYPES.join(', ')}
              </Typography>
              <Typography variant="caption" color="textSecondary" align="center">
                拖拽文件到此区域或点击按钮选择文件
              </Typography>
            </Paper>

            {/* 高级设置切换按钮 */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
              <Button
                startIcon={<SettingsIcon />}
                color="inherit"
                onClick={() => setShowAdvanced(!showAdvanced)}
                size="small"
              >
                {showAdvanced ? '隐藏高级设置' : '显示高级设置'}
              </Button>
            </Box>

            {/* 选中文件列表 */}
            {files.length > 0 && (
              <Card sx={{ mt: 3 }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">
                      已选择的文件 ({files.length})
                    </Typography>
                    <Button
                      size="small"
                      onClick={handleClearFiles}
                      disabled={uploadStatus === UPLOAD_STATUS.UPLOADING || uploadStatus === UPLOAD_STATUS.PROCESSING}
                    >
                      清除全部
                    </Button>
                  </Box>
                  <Divider sx={{ mb: 2 }} />

                  {files.map((fileObj, index) => (
                    <Box key={fileObj.id} sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        {getStatusIcon(fileObj.status)}
                        <Typography variant="body1" sx={{ ml: 1, flexGrow: 1 }} noWrap>
                          {fileObj.file.name}
                          {fileObj.hasDuplicates && (
                            <Chip 
                              size="small" 
                              label="可能重复" 
                              color="warning" 
                              icon={<WarningIcon />}
                              sx={{ ml: 1 }}
                            />
                          )}
                        </Typography>
                        <Typography variant="caption" color="textSecondary" sx={{ mx: 1 }}>
                          {(fileObj.file.size / 1024 / 1024).toFixed(2)} MB
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteFile(fileObj.id)}
                          disabled={uploadStatus === UPLOAD_STATUS.UPLOADING || uploadStatus === UPLOAD_STATUS.PROCESSING}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Box>

                      {fileObj.status === UPLOAD_STATUS.UPLOADING && (
                        <LinearProgress variant="determinate" value={fileObj.progress} sx={{ height: 5, borderRadius: 5 }} />
                      )}

                      {fileObj.status === UPLOAD_STATUS.PROCESSING && (
                        <LinearProgress sx={{ height: 5, borderRadius: 5 }} />
                      )}

                      {fileObj.status === UPLOAD_STATUS.ERROR && (
                        <Typography variant="caption" color="error">
                          错误: {fileObj.error}
                        </Typography>
                      )}

                      {fileObj.status === UPLOAD_STATUS.SUCCESS && fileObj.metadata && (
                        <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {Object.entries(fileObj.metadata)
                            .filter(([key, value]) => value && key !== 'document_id')
                            .map(([key, value]) => (
                              <Chip key={key} size="small" label={`${key}: ${value}`} />
                            ))}
                        </Box>
                      )}

                      {index < files.length - 1 && <Divider sx={{ mt: 2 }} />}
                    </Box>
                  ))}

                  {uploadStatus !== UPLOAD_STATUS.READY && (
                    <Alert severity="info" sx={{ mt: 2 }}>
                      <AlertTitle>
                        {uploadStatus === UPLOAD_STATUS.UPLOADING 
                          ? `正在上传: ${processingFile} (${uploadProgress}%)`
                          : `正在处理: ${processingFile}`}
                      </AlertTitle>
                      {uploadStatus === UPLOAD_STATUS.UPLOADING && (
                        <LinearProgress variant="determinate" value={uploadProgress} sx={{ mt: 1 }} />
                      )}
                      {uploadStatus === UPLOAD_STATUS.PROCESSING && (
                        <LinearProgress sx={{ mt: 1 }} />
                      )}
                    </Alert>
                  )}

                  <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
                    <Button
                      variant="contained"
                      color="primary"
                      startIcon={<CloudUploadIcon />}
                      onClick={handleUpload}
                      disabled={
                        files.length === 0 || 
                        uploadStatus === UPLOAD_STATUS.UPLOADING || 
                        uploadStatus === UPLOAD_STATUS.PROCESSING ||
                        files.every(file => file.status === UPLOAD_STATUS.SUCCESS)
                      }
                      sx={{ minWidth: 150 }}
                    >
                      {uploadStatus === UPLOAD_STATUS.UPLOADING 
                        ? '上传中...' 
                        : uploadStatus === UPLOAD_STATUS.PROCESSING
                          ? '处理中...'
                          : '开始上传'}
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            )}
          </Grid>

          {/* 高级设置面板 */}
          {showAdvanced && (
            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    高级设置
                  </Typography>
                  <Divider sx={{ mb: 2 }} />

                  <FormGroup sx={{ mb: 2 }}>
                    <FormControl fullWidth sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        文本分块方式
                      </Typography>
                      <Select
                        value={config.chunker}
                        onChange={(e) => handleConfigChange('chunker', e.target.value)}
                        disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        size="small"
                      >
                        <MenuItem value="recursive">递归分块</MenuItem>
                        <MenuItem value="simple">简单分块</MenuItem>
                        <MenuItem value="sentence">句子分块</MenuItem>
                      </Select>
                      <FormHelperText>
                        定义如何将文档拆分为可检索的块
                      </FormHelperText>
                    </FormControl>

                    <FormControl fullWidth sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        块大小 (字符数)
                      </Typography>
                      <TextField
                        type="number"
                        value={config.chunkSize}
                        onChange={(e) => handleConfigChange('chunkSize', parseInt(e.target.value))}
                        disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        size="small"
                        InputProps={{ inputProps: { min: 100, max: 4000 } }}
                      />
                      <FormHelperText>
                        每个文本块的最大字符数 (100-4000)
                      </FormHelperText>
                    </FormControl>

                    <FormControl fullWidth sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        块重叠 (字符数)
                      </Typography>
                      <TextField
                        type="number"
                        value={config.chunkOverlap}
                        onChange={(e) => handleConfigChange('chunkOverlap', parseInt(e.target.value))}
                        disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        size="small"
                        InputProps={{ inputProps: { min: 0, max: config.chunkSize / 2 } }}
                      />
                      <FormHelperText>
                        相邻块之间的重叠字符数
                      </FormHelperText>
                    </FormControl>

                    <FormControl fullWidth sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        可选索引名称
                      </Typography>
                      <TextField
                        value={config.indexName}
                        onChange={(e) => handleConfigChange('indexName', e.target.value)}
                        disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        size="small"
                        placeholder="默认使用系统索引"
                      />
                      <FormHelperText>
                        自定义索引名称 (可选)
                      </FormHelperText>
                    </FormControl>

                    <FormControlLabel
                      control={
                        <Switch
                          checked={config.metadataExtraction}
                          onChange={(e) => handleConfigChange('metadataExtraction', e.target.checked)}
                          disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        />
                      }
                      label="提取文档元数据"
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={config.languageDetection}
                          onChange={(e) => handleConfigChange('languageDetection', e.target.checked)}
                          disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        />
                      }
                      label="自动检测语言"
                    />

                    <FormControlLabel
                      control={
                        <Switch
                          checked={config.extractImages}
                          onChange={(e) => handleConfigChange('extractImages', e.target.checked)}
                          disabled={uploadStatus !== UPLOAD_STATUS.READY}
                        />
                      }
                      label="提取文档图片 (实验性)"
                    />
                  </FormGroup>
                </CardContent>
              </Card>
            </Grid>
          )}
        </Grid>
        
        {/* 重复文件警告对话框 */}
        <Dialog
          open={duplicateFileDialog}
          onClose={handleCloseDuplicateDialog}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle sx={{ display: 'flex', alignItems: 'center' }}>
            <WarningIcon color="warning" sx={{ mr: 1 }} />
            发现可能重复的文档
          </DialogTitle>
          <DialogContent>
            <DialogContentText paragraph>
              以下文件可能与已有文档重复。您可以选择继续上传所有文件，或移除重复文件。
            </DialogContentText>
            <List sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
              {duplicateFiles.map((item, index) => (
                <React.Fragment key={`duplicate-${index}`}>
                  <ListItem alignItems="flex-start">
                    <ListItemText
                      primary={<Typography fontWeight="bold">{item.file.name}</Typography>}
                      secondary={
                        <Box>
                          <Typography component="span" variant="body2" color="text.primary">
                            大小: {(item.file.size / 1024 / 1024).toFixed(2)} MB
                          </Typography>
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            可能与以下已有文档重复:
                          </Typography>
                          <List dense disablePadding>
                            {item.duplicates.map((duplicate, dupIndex) => (
                              <ListItem key={`dup-item-${dupIndex}`} dense sx={{ pl: 2 }}>
                                <ListItemText
                                  primary={duplicate.name}
                                  secondary={`大小: ${formatFileSize(duplicate.file_size)} - 上传时间: ${formatDate(duplicate.upload_date)}`}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Box>
                      }
                    />
                  </ListItem>
                  {index < duplicateFiles.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleRemoveDuplicates} color="primary">
              移除重复文件
            </Button>
            <Button onClick={handleKeepAllFiles} color="warning">
              继续上传所有文件
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
  
  // 格式化文件大小的辅助函数
  function formatFileSize(bytes) {
    if (!bytes) return 'N/A';
    
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
  }
  
  // 格式化日期的辅助函数
  function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    return new Date(dateString).toLocaleString();
  }
}

export default Upload; 