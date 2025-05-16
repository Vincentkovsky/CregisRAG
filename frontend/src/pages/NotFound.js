import React from 'react';
import { Box, Button, Container, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import ErrorIcon from '@mui/icons-material/Error';
import HomeIcon from '@mui/icons-material/Home';

function NotFound() {
  const navigate = useNavigate();

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '70vh',
          textAlign: 'center',
          py: 8,
        }}
      >
        <ErrorIcon sx={{ fontSize: 100, color: 'error.light', mb: 4 }} />
        
        <Typography variant="h1" component="h1" gutterBottom>
          404
        </Typography>
        
        <Typography variant="h4" component="h2" gutterBottom>
          页面未找到
        </Typography>
        
        <Typography variant="body1" color="textSecondary" paragraph sx={{ maxWidth: 600, mb: 4 }}>
          您尝试访问的页面不存在或已被移动。请检查URL是否正确，或返回首页继续浏览。
        </Typography>
        
        <Button 
          variant="contained" 
          color="primary" 
          size="large"
          startIcon={<HomeIcon />}
          onClick={() => navigate('/')}
        >
          返回首页
        </Button>
      </Box>
    </Container>
  );
}

export default NotFound; 