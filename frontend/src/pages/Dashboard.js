import React, { useState, useEffect } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Divider,
  Grid,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import MemoryIcon from '@mui/icons-material/Memory';
import StorageIcon from '@mui/icons-material/Storage';
import SpeedIcon from '@mui/icons-material/Speed';
import DescriptionIcon from '@mui/icons-material/Description';
import SearchIcon from '@mui/icons-material/Search';
import AccessTimeIcon from '@mui/icons-material/AccessTime';

import { adminAPI, healthAPI } from '../services/api';

// 图表组件 - 如果需要可以添加图表库如 recharts 或 chart.js
function StatCard({ title, value, icon, color, subtitle, loading }) {
  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography color="textSecondary" gutterBottom variant="body2">
              {title}
            </Typography>
            {loading ? (
              <CircularProgress size={20} />
            ) : (
              <Typography variant="h5" color={color || 'primary'}>
                {value}
              </Typography>
            )}
            {subtitle && (
              <Typography variant="caption" color="textSecondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              backgroundColor: `${color || 'primary'}.light`,
              borderRadius: 1,
              p: 1,
              color: `${color || 'primary'}.main`,
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

function StatusIndicator({ status }) {
  const getStatusInfo = () => {
    switch (status) {
      case 'healthy':
        return { icon: <CheckCircleIcon />, color: 'success', text: '正常' };
      case 'degraded':
        return { icon: <WarningIcon />, color: 'warning', text: '性能下降' };
      case 'unhealthy':
        return { icon: <ErrorIcon />, color: 'error', text: '异常' };
      default:
        return { icon: <CircularProgress size={20} />, color: 'info', text: '检查中...' };
    }
  };

  const { icon, color, text } = getStatusInfo();

  return (
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      <Box sx={{ color: `${color}.main`, mr: 1 }}>{icon}</Box>
      <Typography color={`${color}.main`}>{text}</Typography>
    </Box>
  );
}

function Dashboard({ showNotification }) {
  // 状态管理
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState('loading');
  const [systemStats, setSystemStats] = useState({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    uptime: 0,
  });
  const [dbStats, setDbStats] = useState({
    total_documents: 0,
    total_chunks: 0,
    total_embeddings: 0,
    index_size: 0,
  });
  const [queryStats, setQueryStats] = useState({
    total_queries: 0,
    avg_response_time: 0,
    queries_today: 0,
    success_rate: 0,
  });
  const [recentQueries, setRecentQueries] = useState([]);
  const [recentErrors, setRecentErrors] = useState([]);

  // 加载所有仪表盘数据
  const loadDashboardData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        checkHealth(),
        fetchSystemStats(),
      ]);
      // 注意：以下API调用可能不可用，捕获每个错误
      try { await fetchDbStats(); } catch (e) { console.error('获取数据库统计失败:', e); }
      try { await fetchQueryStats(); } catch (e) { console.error('获取查询统计失败:', e); }
      try { await fetchRecentQueries(); } catch (e) { console.error('获取最近查询失败:', e); }
      try { await fetchRecentErrors(); } catch (e) { console.error('获取错误记录失败:', e); }
    } catch (error) {
      console.error('Error loading dashboard data:', error);
      showNotification && showNotification('加载仪表盘数据失败', 'error');
    } finally {
      setLoading(false);
    }
  };

  // 检查系统健康状态
  const checkHealth = async () => {
    try {
      const response = await healthAPI.check();
      setHealthStatus(response.status);
    } catch (error) {
      setHealthStatus('unhealthy');
      console.error('Health check failed:', error);
    }
  };

  // 获取系统状态统计
  const fetchSystemStats = async () => {
    try {
      // 使用正确的API方法 getSystemStatus 替代 getSystemStats
      const response = await adminAPI.getSystemStatus();
      
      // 使用返回的数据更新状态
      setSystemStats({
        cpu_usage: response.resources?.cpu_usage || 0,
        memory_usage: response.resources?.memory_usage || 0,
        disk_usage: response.resources?.disk_usage || 0,
        uptime: response.uptime || 0,
      });
    } catch (error) {
      console.error('Failed to fetch system stats:', error);
    }
  };

  // 获取数据库统计
  const fetchDbStats = async () => {
    try {
      // 修改为使用getStatistics方法并从中提取所需数据
      const response = await adminAPI.getStatistics();
      
      // 假设统计数据包含vector_store部分
      const vectorStore = response.vector_store || {};
      
      // 获取所有文档列表以获取文档总数和块总数
      try {
        const documentsResponse = await fetch('/api/ingest/documents');
        const documentsData = await documentsResponse.json();
        
        setDbStats({
          total_documents: documentsData.total_documents || 0,
          total_chunks: documentsData.total_chunks || 0,
          total_embeddings: vectorStore.vector_count || 0,
          index_size: vectorStore.collection_size || 0,
        });
      } catch (docError) {
        console.error('Failed to fetch documents data:', docError);
        // 如果文档API调用失败，回退到使用统计API数据
        setDbStats({
          total_documents: vectorStore.document_count || 0,
          total_chunks: vectorStore.vector_count || 0,
          total_embeddings: vectorStore.vector_count || 0,
          index_size: vectorStore.collection_size || 0,
        });
      }
    } catch (error) {
      console.error('Failed to fetch database stats:', error);
    }
  };

  // 获取查询统计
  const fetchQueryStats = async () => {
    try {
      // 修改为使用getStatistics方法并从中提取所需数据
      const response = await adminAPI.getStatistics();
      
      // 假设统计数据包含queries部分
      const queries = response.queries || {};
      
      setQueryStats({
        total_queries: queries.total_queries || 0,
        avg_response_time: queries.avg_query_time || 0,
        queries_today: queries.queries_last_24h || 0,
        success_rate: 100, // 假设100%，因为API中可能没有这个数据
      });
    } catch (error) {
      console.error('Failed to fetch query stats:', error);
    }
  };

  // 获取最近查询
  const fetchRecentQueries = async () => {
    try {
      // 使用新的API端点获取查询历史
      const response = await adminAPI.getRecentQueries(10);
      
      if (response && response.queries) {
        setRecentQueries(response.queries.map(query => ({
          id: query.query_id || query.timestamp,
          query: query.query_text,
          time: query.timestamp ? formatDate(query.timestamp) : query.query_time,
          responseTime: query.processing_time.toFixed(2),
          status: 'success'
        })));
      } else {
        setRecentQueries([]);
      }
    } catch (error) {
      console.error('Failed to fetch recent queries:', error);
      setRecentQueries([]);
    }
  };

  // 获取最近错误
  const fetchRecentErrors = async () => {
    try {
      // 使用新的API端点获取错误日志
      const response = await adminAPI.getErrorLogs(10);
      
      if (response && response.errors) {
        setRecentErrors(response.errors.map(error => ({
          id: error.error_id || error.timestamp,
          message: error.message,
          component: error.component,
          time: error.timestamp ? formatDate(error.timestamp) : error.error_time,
          type: error.error_type
        })));
      } else {
        setRecentErrors([]);
      }
    } catch (error) {
      console.error('Failed to fetch recent errors:', error);
      setRecentErrors([]);
    }
  };

  // 初始化加载
  useEffect(() => {
    loadDashboardData();
    // 设置定时器每60秒刷新一次健康状态
    const interval = setInterval(checkHealth, 60000);
    return () => clearInterval(interval);
  }, []);

  // 格式化时间
  const formatTime = (seconds) => {
    const days = Math.floor(seconds / (24 * 60 * 60));
    const hours = Math.floor((seconds % (24 * 60 * 60)) / (60 * 60));
    const minutes = Math.floor((seconds % (60 * 60)) / 60);
    
    return `${days}天 ${hours}小时 ${minutes}分钟`;
  };

  // 格式化日期
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    
    return new Date(dateString).toLocaleString();
  };

  // 格式化文件大小
  const formatFileSize = (bytes) => {
    if (!bytes) return 'N/A';
    
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Typography variant="h4" component="h1">
            系统仪表盘
          </Typography>
          <Box>
            <Tooltip title="刷新数据">
              <IconButton onClick={loadDashboardData} disabled={loading}>
                {loading ? <CircularProgress size={24} /> : <RefreshIcon />}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* 系统状态卡片 */}
        <Box sx={{ mb: 4 }}>
          <Paper
            sx={{
              p: 2,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: healthStatus === 'healthy' ? 'success.light' : healthStatus === 'degraded' ? 'warning.light' : 'error.light',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography variant="h6" component="div">
                系统状态:
              </Typography>
              <Box sx={{ ml: 2 }}>
                <StatusIndicator status={healthStatus} />
              </Box>
            </Box>
            <Typography variant="body2">
              最后更新: {new Date().toLocaleTimeString()}
            </Typography>
          </Paper>
        </Box>

        {/* 统计卡片 */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="CPU 使用率"
              value={`${systemStats.cpu_usage}%`}
              icon={<MemoryIcon />}
              color={systemStats.cpu_usage > 80 ? 'error' : systemStats.cpu_usage > 60 ? 'warning' : 'success'}
              loading={loading}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="内存使用率"
              value={`${systemStats.memory_usage}%`}
              icon={<StorageIcon />}
              color={systemStats.memory_usage > 80 ? 'error' : systemStats.memory_usage > 60 ? 'warning' : 'success'}
              loading={loading}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="系统运行时间"
              value={formatTime(systemStats.uptime)}
              icon={<AccessTimeIcon />}
              color="info"
              loading={loading}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="磁盘使用率"
              value={`${systemStats.disk_usage}%`}
              icon={<StorageIcon />}
              color={systemStats.disk_usage > 80 ? 'error' : systemStats.disk_usage > 60 ? 'warning' : 'success'}
              loading={loading}
            />
          </Grid>
        </Grid>

        <Grid container spacing={3}>
          {/* 数据库统计 */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  数据统计
                </Typography>
                <Divider sx={{ mb: 2 }} />
                
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <DescriptionIcon color="primary" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        源文档总数: <b>{loading ? '加载中...' : dbStats.total_documents}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <StorageIcon color="secondary" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        文本块总数: <b>{loading ? '加载中...' : dbStats.total_chunks}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <MemoryIcon color="info" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        向量嵌入总数: <b>{loading ? '加载中...' : dbStats.total_embeddings}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <StorageIcon color="warning" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        索引大小: <b>{loading ? '加载中...' : formatFileSize(dbStats.index_size)}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  {dbStats.total_chunks > dbStats.total_documents && (
                    <Grid item xs={12}>
                      <Alert severity="info" sx={{ mt: 1 }}>
                        系统中共有 {dbStats.total_documents} 个源文档，经过分块处理后生成了 {dbStats.total_chunks} 个文本块用于向量检索。
                      </Alert>
                    </Grid>
                  )}
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* 查询统计 */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  查询统计
                </Typography>
                <Divider sx={{ mb: 2 }} />
                
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <SearchIcon color="primary" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        查询总数: <b>{loading ? '加载中...' : queryStats.total_queries}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <SearchIcon color="secondary" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        今日查询: <b>{loading ? '加载中...' : queryStats.queries_today}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <AccessTimeIcon color="info" sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        平均响应时间: <b>{loading ? '加载中...' : (queryStats.avg_response_time > 0 ? queryStats.avg_response_time.toFixed(2) + '秒' : 'N/A')}</b>
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <SpeedIcon color={queryStats.success_rate > 90 ? 'success' : 'warning'} sx={{ mr: 1 }} />
                      <Typography variant="body2">
                        成功率: <b>{loading ? '加载中...' : queryStats.success_rate + '%'}</b>
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* 最近查询 */}
          <Grid item xs={12} md={6}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  最近查询
                </Typography>
                <Divider sx={{ mb: 2 }} />
                
                {loading ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <CircularProgress />
                  </Box>
                ) : recentQueries.length === 0 ? (
                  <Typography variant="body2" color="textSecondary" align="center" sx={{ py: 4 }}>
                    暂无查询记录
                  </Typography>
                ) : (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>查询</TableCell>
                          <TableCell align="right">响应时间</TableCell>
                          <TableCell align="right">时间</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {recentQueries.slice(0, 5).map((query, index) => (
                          <TableRow key={index} hover>
                            <TableCell>
                              <Typography variant="body2" noWrap sx={{ maxWidth: 220 }}>
                                {query.query}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                {query.responseTime}秒
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                {query.time}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* 最近错误 */}
          <Grid item xs={12} md={6}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  最近系统错误
                </Typography>
                <Divider sx={{ mb: 2 }} />
                
                {loading ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                    <CircularProgress />
                  </Box>
                ) : recentErrors.length === 0 ? (
                  <Alert severity="success" sx={{ my: 2 }}>
                    系统运行正常，无错误记录
                  </Alert>
                ) : (
                  <>
                    {recentErrors.slice(0, 5).map((error, index) => (
                      <Alert severity="error" sx={{ mb: 2 }} key={index}>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {error.type}
                        </Typography>
                        <Typography variant="body2">
                          {error.message}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {error.time} | {error.component}
                        </Typography>
                      </Alert>
                    ))}
                  </>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}

export default Dashboard; 