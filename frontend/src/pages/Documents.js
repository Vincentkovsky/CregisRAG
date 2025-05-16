import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
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
  Grid,
  IconButton,
  InputAdornment,
  Menu,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import InfoIcon from '@mui/icons-material/Info';
import DownloadIcon from '@mui/icons-material/Download';
import FilterListIcon from '@mui/icons-material/FilterList';
import CloseIcon from '@mui/icons-material/Close';
import { useNavigate } from 'react-router-dom';

import { ingestAPI } from '../services/api';

function Documents({ showNotification }) {
  const navigate = useNavigate();
  
  // 状态管理
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [orderBy, setOrderBy] = useState('upload_date');
  const [order, setOrder] = useState('desc');
  const [actionMenuAnchor, setActionMenuAnchor] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [documentDetailsOpen, setDocumentDetailsOpen] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [filters, setFilters] = useState({
    fileType: '',
    status: '',
    dateFrom: '',
    dateTo: '',
  });
  
  // 获取文档列表
  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await ingestAPI.getAllDocuments();
      setDocuments(response.documents || []);
    } catch (error) {
      showNotification(
        error.message || '获取文档列表失败',
        'error'
      );
    } finally {
      setLoading(false);
    }
  };

  // 初始化加载
  useEffect(() => {
    fetchDocuments();
  }, []);

  // 修复React Hook依赖警告
  useEffect(() => {
    // 组件挂载时获取文档
    fetchDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 处理排序
  const handleRequestSort = (property) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  // 处理页面变更
  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  // 处理每页行数变更
  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  // 处理搜索
  const handleSearch = (event) => {
    setSearchTerm(event.target.value);
    setPage(0);
  };

  // 打开操作菜单
  const handleOpenActionMenu = (event, document) => {
    setActionMenuAnchor(event.currentTarget);
    setSelectedDocument(document);
  };

  // 关闭操作菜单
  const handleCloseActionMenu = () => {
    setActionMenuAnchor(null);
  };

  // 查看文档详情
  const handleViewDetails = () => {
    setDocumentDetailsOpen(true);
    handleCloseActionMenu();
  };

  // 下载文档
  const handleDownload = async () => {
    if (!selectedDocument) return;
    
    try {
      await ingestAPI.downloadDocument(selectedDocument.document_id);
      showNotification('文档下载成功', 'success');
    } catch (error) {
      showNotification(
        error.message || '下载文档失败',
        'error'
      );
    }
    
    handleCloseActionMenu();
  };

  // 删除文档
  const handleDeleteConfirm = () => {
    setConfirmDeleteOpen(true);
    handleCloseActionMenu();
  };

  // 确认删除
  const handleDelete = async () => {
    if (!selectedDocument) return;
    
    try {
      await ingestAPI.deleteDocument(selectedDocument.document_id);
      showNotification('文档已删除', 'success');
      fetchDocuments(); // 刷新列表
    } catch (error) {
      showNotification(
        error.message || '删除文档失败',
        'error'
      );
    }
    
    setConfirmDeleteOpen(false);
  };

  // 刷新文档列表
  const handleRefresh = () => {
    fetchDocuments();
  };

  // 切换筛选面板
  const toggleFiltering = () => {
    setFiltering(!filtering);
  };

  // 更新筛选条件
  const handleFilterChange = (field, value) => {
    setFilters({
      ...filters,
      [field]: value,
    });
    setPage(0);
  };

  // 清除所有筛选条件
  const clearFilters = () => {
    setFilters({
      fileType: '',
      status: '',
      dateFrom: '',
      dateTo: '',
    });
    setPage(0);
  };

  // 获取文档状态标签颜色
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'processing':
        return 'info';
      case 'failed':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes) => {
    if (!bytes) return 'N/A';
    
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
  };

  // 格式化日期
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    
    return new Date(dateString).toLocaleString();
  };

  // 应用筛选和搜索
  const filteredDocuments = documents.filter((document) => {
    // 搜索词过滤
    const searchMatch = !searchTerm || 
      document.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (document.metadata?.title && document.metadata.title.toLowerCase().includes(searchTerm.toLowerCase()));
    
    // 文件类型过滤
    const fileTypeMatch = !filters.fileType || 
      document.file_type?.toLowerCase() === filters.fileType.toLowerCase();
    
    // 状态过滤
    const statusMatch = !filters.status || 
      document.status?.toLowerCase() === filters.status.toLowerCase();
    
    // 日期从
    const dateFromMatch = !filters.dateFrom || 
      new Date(document.upload_date) >= new Date(filters.dateFrom);
    
    // 日期到
    const dateToMatch = !filters.dateTo || 
      new Date(document.upload_date) <= new Date(filters.dateTo);
    
    return searchMatch && fileTypeMatch && statusMatch && dateFromMatch && dateToMatch;
  });

  // 排序
  const sortedDocuments = filteredDocuments.sort((a, b) => {
    const isAsc = order === 'asc';
    
    switch (orderBy) {
      case 'name':
        return isAsc 
          ? a.name.localeCompare(b.name) 
          : b.name.localeCompare(a.name);
      case 'file_type':
        return isAsc 
          ? (a.file_type || '').localeCompare(b.file_type || '') 
          : (b.file_type || '').localeCompare(a.file_type || '');
      case 'file_size':
        return isAsc 
          ? (a.file_size || 0) - (b.file_size || 0) 
          : (b.file_size || 0) - (a.file_size || 0);
      case 'status':
        return isAsc 
          ? (a.status || '').localeCompare(b.status || '') 
          : (b.status || '').localeCompare(a.status || '');
      case 'upload_date':
      default:
        return isAsc 
          ? new Date(a.upload_date) - new Date(b.upload_date) 
          : new Date(b.upload_date) - new Date(a.upload_date);
    }
  });

  // 分页
  const paginatedDocuments = sortedDocuments.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  // 提取唯一的文件类型列表
  const fileTypes = [...new Set(documents.map(doc => doc.file_type).filter(Boolean))];

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          文档管理
        </Typography>

        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <TextField
            placeholder="搜索文档..."
            value={searchTerm}
            onChange={handleSearch}
            variant="outlined"
            size="small"
            sx={{ width: 300 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon color="action" />
                </InputAdornment>
              ),
            }}
          />
          <Box>
            <Tooltip title="筛选文档">
              <IconButton onClick={toggleFiltering} color={filtering ? 'primary' : 'default'}>
                <FilterListIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="刷新列表">
              <IconButton onClick={handleRefresh} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Button
              variant="contained"
              onClick={() => navigate('/upload')}
              sx={{ ml: 2 }}
            >
              上传新文档
            </Button>
          </Box>
        </Box>

        {/* 筛选面板 */}
        {filtering && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="subtitle1">筛选条件</Typography>
              <Button size="small" onClick={clearFilters}>
                清除筛选
              </Button>
            </Box>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
              <FormControl sx={{ minWidth: 150 }}>
                <TextField
                  select
                  size="small"
                  label="文件类型"
                  value={filters.fileType}
                  onChange={(e) => handleFilterChange('fileType', e.target.value)}
                >
                  <MenuItem value="">全部</MenuItem>
                  {fileTypes.map((type) => (
                    <MenuItem key={type} value={type}>
                      {type.toUpperCase()}
                    </MenuItem>
                  ))}
                </TextField>
              </FormControl>
              <FormControl sx={{ minWidth: 150 }}>
                <TextField
                  select
                  size="small"
                  label="状态"
                  value={filters.status}
                  onChange={(e) => handleFilterChange('status', e.target.value)}
                >
                  <MenuItem value="">全部</MenuItem>
                  <MenuItem value="completed">已完成</MenuItem>
                  <MenuItem value="processing">处理中</MenuItem>
                  <MenuItem value="failed">失败</MenuItem>
                  <MenuItem value="pending">等待中</MenuItem>
                </TextField>
              </FormControl>
              <TextField
                size="small"
                label="上传日期从"
                type="date"
                value={filters.dateFrom}
                onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                size="small"
                label="上传日期至"
                type="date"
                value={filters.dateTo}
                onChange={(e) => handleFilterChange('dateTo', e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Box>
          </Paper>
        )}

        {/* 文档表格 */}
        <Paper sx={{ width: '100%', overflow: 'hidden' }}>
          <TableContainer sx={{ maxHeight: 600 }}>
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>
                    <TableSortLabel
                      active={orderBy === 'name'}
                      direction={orderBy === 'name' ? order : 'asc'}
                      onClick={() => handleRequestSort('name')}
                    >
                      文档名称
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="center">
                    <TableSortLabel
                      active={orderBy === 'file_type'}
                      direction={orderBy === 'file_type' ? order : 'asc'}
                      onClick={() => handleRequestSort('file_type')}
                    >
                      类型
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="center">
                    <TableSortLabel
                      active={orderBy === 'file_size'}
                      direction={orderBy === 'file_size' ? order : 'asc'}
                      onClick={() => handleRequestSort('file_size')}
                    >
                      大小
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="center">
                    <TableSortLabel
                      active={orderBy === 'status'}
                      direction={orderBy === 'status' ? order : 'asc'}
                      onClick={() => handleRequestSort('status')}
                    >
                      状态
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="center">
                    <TableSortLabel
                      active={orderBy === 'upload_date'}
                      direction={orderBy === 'upload_date' ? order : 'asc'}
                      onClick={() => handleRequestSort('upload_date')}
                    >
                      上传时间
                    </TableSortLabel>
                  </TableCell>
                  <TableCell align="center">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 5 }}>
                      <CircularProgress />
                      <Typography variant="body2" sx={{ mt: 2 }}>
                        加载文档列表...
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : paginatedDocuments.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 5 }}>
                      {searchTerm || filtering ? (
                        <>
                          <Typography variant="body1">
                            没有找到匹配的文档
                          </Typography>
                          <Typography variant="body2" color="textSecondary">
                            尝试修改搜索条件或筛选条件
                          </Typography>
                        </>
                      ) : (
                        <>
                          <Typography variant="body1">
                            还没有文档
                          </Typography>
                          <Button
                            variant="contained"
                            onClick={() => navigate('/upload')}
                            sx={{ mt: 2 }}
                          >
                            上传文档
                          </Button>
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedDocuments.map((document) => (
                    <TableRow key={document.document_id} hover>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 300 }}>
                          {document.name}
                        </Typography>
                        {document.metadata?.title && (
                          <Typography variant="caption" color="textSecondary" display="block" noWrap>
                            {document.metadata.title}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell align="center">
                        <Chip 
                          label={document.file_type?.toUpperCase() || 'N/A'} 
                          size="small" 
                          color="primary"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell align="center">
                        {formatFileSize(document.file_size)}
                      </TableCell>
                      <TableCell align="center">
                        <Chip 
                          label={document.status?.charAt(0).toUpperCase() + document.status?.slice(1) || 'N/A'} 
                          size="small" 
                          color={getStatusColor(document.status)}
                        />
                      </TableCell>
                      <TableCell align="center">
                        {formatDate(document.upload_date)}
                      </TableCell>
                      <TableCell align="center">
                        <IconButton
                          aria-label="更多操作"
                          onClick={(event) => handleOpenActionMenu(event, document)}
                          size="small"
                        >
                          <MoreVertIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            rowsPerPageOptions={[5, 10, 25, 50]}
            component="div"
            count={filteredDocuments.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            labelRowsPerPage="每页行数:"
            labelDisplayedRows={({ from, to, count }) => `${from}-${to} / ${count}`}
          />
        </Paper>

        {/* 操作菜单 */}
        <Menu
          anchorEl={actionMenuAnchor}
          open={Boolean(actionMenuAnchor)}
          onClose={handleCloseActionMenu}
        >
          <MenuItem onClick={handleViewDetails}>
            <InfoIcon fontSize="small" sx={{ mr: 1 }} />
            查看详情
          </MenuItem>
          <MenuItem onClick={handleDownload}>
            <DownloadIcon fontSize="small" sx={{ mr: 1 }} />
            下载文档
          </MenuItem>
          <Divider />
          <MenuItem onClick={handleDeleteConfirm} sx={{ color: 'error.main' }}>
            <DeleteIcon fontSize="small" sx={{ mr: 1 }} />
            删除文档
          </MenuItem>
        </Menu>

        {/* 删除确认对话框 */}
        <Dialog
          open={confirmDeleteOpen}
          onClose={() => setConfirmDeleteOpen(false)}
        >
          <DialogTitle>确认删除</DialogTitle>
          <DialogContent>
            <DialogContentText>
              您确定要删除文档 "{selectedDocument?.name}" 吗？此操作不可撤销。
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmDeleteOpen(false)}>
              取消
            </Button>
            <Button onClick={handleDelete} color="error" autoFocus>
              删除
            </Button>
          </DialogActions>
        </Dialog>

        {/* 文档详情对话框 */}
        <Dialog
          open={documentDetailsOpen}
          onClose={() => setDocumentDetailsOpen(false)}
          maxWidth="md"
          fullWidth
        >
          {selectedDocument && (
            <>
              <DialogTitle>
                文档详情
                <IconButton
                  aria-label="close"
                  onClick={() => setDocumentDetailsOpen(false)}
                  sx={{ position: 'absolute', right: 8, top: 8 }}
                >
                  <CloseIcon />
                </IconButton>
              </DialogTitle>
              <DialogContent dividers>
                <Box sx={{ mb: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    基本信息
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2">文档名称</Typography>
                      <Typography variant="body2">{selectedDocument.name}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2">文档ID</Typography>
                      <Typography variant="body2">{selectedDocument.document_id}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2">文件类型</Typography>
                      <Typography variant="body2">{selectedDocument.file_type?.toUpperCase() || 'N/A'}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2">文件大小</Typography>
                      <Typography variant="body2">{formatFileSize(selectedDocument.file_size)}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2">上传时间</Typography>
                      <Typography variant="body2">{formatDate(selectedDocument.upload_date)}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="subtitle2">处理状态</Typography>
                      <Chip 
                        label={selectedDocument.status?.charAt(0).toUpperCase() + selectedDocument.status?.slice(1) || 'N/A'} 
                        size="small" 
                        color={getStatusColor(selectedDocument.status)}
                      />
                    </Grid>
                  </Grid>
                </Box>
                
                {selectedDocument.processing_details && (
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="h6" gutterBottom>
                      处理信息
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">处理时间</Typography>
                        <Typography variant="body2">
                          {selectedDocument.processing_details.processing_time ? 
                            `${selectedDocument.processing_details.processing_time.toFixed(2)}秒` : 
                            'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">文本块数量</Typography>
                        <Typography variant="body2">
                          {selectedDocument.processing_details.chunk_count || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">分块方式</Typography>
                        <Typography variant="body2">
                          {selectedDocument.processing_details.chunker || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2">所属索引</Typography>
                        <Typography variant="body2">
                          {selectedDocument.processing_details.index_name || '默认索引'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                )}
                
                {selectedDocument.metadata && Object.keys(selectedDocument.metadata).length > 0 && (
                  <Box>
                    <Typography variant="h6" gutterBottom>
                      元数据
                    </Typography>
                    <Grid container spacing={2}>
                      {Object.entries(selectedDocument.metadata)
                        .filter(([key]) => key !== 'document_id')
                        .map(([key, value]) => (
                          <Grid item xs={12} sm={6} key={key}>
                            <Typography variant="subtitle2">{key}</Typography>
                            <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                              {value || 'N/A'}
                            </Typography>
                          </Grid>
                        ))}
                    </Grid>
                  </Box>
                )}
              </DialogContent>
              <DialogActions>
                <Button onClick={() => setDocumentDetailsOpen(false)}>
                  关闭
                </Button>
              </DialogActions>
            </>
          )}
        </Dialog>
      </Box>
    </Container>
  );
}

export default Documents; 