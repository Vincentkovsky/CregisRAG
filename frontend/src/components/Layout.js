import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  useMediaQuery,
  useTheme,
  Badge,
  Tooltip,
} from '@mui/material';

// 图标
import MenuIcon from '@mui/icons-material/Menu';
import HomeIcon from '@mui/icons-material/Home';
import SearchIcon from '@mui/icons-material/Search';
import UploadIcon from '@mui/icons-material/Upload';
import DescriptionIcon from '@mui/icons-material/Description';
import DashboardIcon from '@mui/icons-material/Dashboard';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import GitHubIcon from '@mui/icons-material/GitHub';

// 抽屉宽度
const drawerWidth = 240;

const menuItems = [
  { text: '首页', path: '/', icon: <HomeIcon /> },
  { text: '知识检索', path: '/search', icon: <SearchIcon /> },
  { text: '上传文档', path: '/upload', icon: <UploadIcon /> },
  { text: '文档管理', path: '/documents', icon: <DescriptionIcon /> },
  { text: '系统状态', path: '/dashboard', icon: <DashboardIcon /> },
];

function Layout({ children, isServerConnected = true }) {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleNavigation = (path) => {
    navigate(path);
    if (isMobile) {
      setMobileOpen(false);
    }
  };

  const drawer = (
    <div>
      <Toolbar sx={{ justifyContent: 'center' }}>
        <Typography variant="h6" noWrap component="div" color="primary.main">
          CregisRAG
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Divider />
      <Box sx={{ p: 2, mt: 'auto' }}>
        <Typography variant="caption" display="block" color="text.secondary" align="center">
          CregisRAG v0.1.0
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
          <Tooltip title="查看源代码">
            <IconButton
              color="inherit"
              size="small"
              onClick={() => window.open('https://github.com/yourusername/CregisRAG', '_blank')}
            >
              <GitHubIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${drawerWidth}px)` },
          ml: { md: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="打开抽屉"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            {menuItems.find((item) => item.path === location.pathname)?.text || '404 未找到'}
          </Typography>
          {!isServerConnected && (
            <Tooltip title="服务器连接中断">
              <Badge color="error" variant="dot">
                <WifiOffIcon color="error" />
              </Badge>
            </Tooltip>
          )}
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
        aria-label="导航菜单"
      >
        {/* 移动端抽屉 */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // 提高移动端性能
          }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        {/* 桌面端抽屉 */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Toolbar />
        <Box sx={{ flexGrow: 1 }}>{children}</Box>
        <Box
          component="footer"
          sx={{
            mt: 'auto',
            py: 2,
            textAlign: 'center',
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            © {new Date().getFullYear()} CregisRAG - 智能检索增强生成系统
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

export default Layout; 