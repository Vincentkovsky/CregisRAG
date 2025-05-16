import React, { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';

// 主题
import theme from './styles/theme';

// 布局组件
import Layout from './components/Layout';

// 页面组件
import Home from './pages/Home';
import Search from './pages/Search';
import Upload from './pages/Upload';
import Documents from './pages/Documents';
import Dashboard from './pages/Dashboard';
import NotFound from './pages/NotFound';

// API
import { healthAPI } from './services/api';

function App() {
  const [notification, setNotification] = useState({
    open: false,
    message: '',
    severity: 'info',
  });
  const [isServerConnected, setIsServerConnected] = useState(true);

  // 检查服务器连接状态
  useEffect(() => {
    const checkServerConnection = async () => {
      try {
        await healthAPI.check();
        setIsServerConnected(true);
      } catch (error) {
        setIsServerConnected(false);
        setNotification({
          open: true,
          message: '无法连接到服务器，部分功能可能不可用',
          severity: 'error',
        });
      }
    };

    checkServerConnection();
    // 每60秒检查一次服务器连接
    const interval = setInterval(checkServerConnection, 60000);
    return () => clearInterval(interval);
  }, []);

  // 处理通知关闭
  const handleCloseNotification = (event, reason) => {
    if (reason === 'clickaway') return;
    setNotification({ ...notification, open: false });
  };

  // 显示通知
  const showNotification = (message, severity = 'info') => {
    setNotification({
      open: true,
      message,
      severity,
    });
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Layout isServerConnected={isServerConnected}>
          <Routes>
            <Route path="/" element={<Home showNotification={showNotification} />} />
            <Route path="/search" element={<Search showNotification={showNotification} />} />
            <Route path="/upload" element={<Upload showNotification={showNotification} />} />
            <Route path="/documents" element={<Documents showNotification={showNotification} />} />
            <Route path="/dashboard" element={<Dashboard showNotification={showNotification} />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>

        {/* 通知组件 */}
        <Snackbar
          open={notification.open}
          autoHideDuration={6000}
          onClose={handleCloseNotification}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert
            onClose={handleCloseNotification}
            severity={notification.severity}
            variant="filled"
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>
      </Box>
    </ThemeProvider>
  );
}

export default App; 