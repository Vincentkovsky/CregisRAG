import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Container,
  Grid,
  Typography,
  Paper,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import UploadIcon from '@mui/icons-material/Upload';
import DescriptionIcon from '@mui/icons-material/Description';
import DashboardIcon from '@mui/icons-material/Dashboard';

function Home() {
  const navigate = useNavigate();

  const features = [
    {
      title: '知识检索',
      description: '基于您的文档，智能回答问题并提供可靠来源',
      icon: <SearchIcon sx={{ fontSize: 40 }} color="primary" />,
      action: () => navigate('/search'),
      buttonText: '开始查询',
    },
    {
      title: '上传文档',
      description: '轻松上传PDF、Word、文本文件或从URL导入内容',
      icon: <UploadIcon sx={{ fontSize: 40 }} color="primary" />,
      action: () => navigate('/upload'),
      buttonText: '上传文档',
    },
    {
      title: '文档管理',
      description: '查看和管理您的知识库中的所有文档',
      icon: <DescriptionIcon sx={{ fontSize: 40 }} color="primary" />,
      action: () => navigate('/documents'),
      buttonText: '查看文档',
    },
    {
      title: '系统状态',
      description: '查看系统性能、统计数据和执行维护操作',
      icon: <DashboardIcon sx={{ fontSize: 40 }} color="primary" />,
      action: () => navigate('/dashboard'),
      buttonText: '系统状态',
    },
  ];

  return (
    <Container>
      <Box sx={{ my: 4, textAlign: 'center' }}>
        <Typography variant="h3" component="h1" gutterBottom color="primary">
          欢迎使用 CregisRAG
        </Typography>
        <Typography variant="h5" component="h2" gutterBottom color="textSecondary">
          智能检索增强生成系统
        </Typography>
        <Typography variant="body1" paragraph sx={{ maxWidth: 700, mx: 'auto', mb: 4 }}>
          CregisRAG 结合了大型语言模型的生成能力与您专有知识库的精确检索功能，提供准确、可靠且有出处的回答。
        </Typography>

        <Grid container spacing={3} justifyContent="center" sx={{ mb: 6 }}>
          {features.map((feature, index) => (
            <Grid item xs={12} sm={6} md={3} key={index}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'transform 0.2s',
                  '&:hover': { transform: 'translateY(-5px)' },
                }}
              >
                <CardContent sx={{ flexGrow: 1, textAlign: 'center' }}>
                  <Box sx={{ mb: 2 }}>{feature.icon}</Box>
                  <Typography variant="h6" component="h3" gutterBottom>
                    {feature.title}
                  </Typography>
                  <Typography variant="body2" color="textSecondary" paragraph>
                    {feature.description}
                  </Typography>
                  <Button
                    variant="contained"
                    size="small"
                    color="primary"
                    onClick={feature.action}
                  >
                    {feature.buttonText}
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        <Paper
          sx={{
            p: 3,
            backgroundColor: 'primary.light',
            color: 'white',
            borderRadius: 2,
            maxWidth: 800,
            mx: 'auto',
          }}
        >
          <Typography variant="h6" gutterBottom>
            开始使用
          </Typography>
          <Typography variant="body1" paragraph>
            1. 上传您的文档或从URL导入内容
          </Typography>
          <Typography variant="body1" paragraph>
            2. 等待系统处理和向量化您的文档
          </Typography>
          <Typography variant="body1" paragraph>
            3. 在搜索页面提问，获取来自您的知识库的精准回答
          </Typography>
          <Button
            variant="contained"
            color="secondary"
            size="large"
            onClick={() => navigate('/upload')}
            sx={{ mt: 2 }}
          >
            立即开始
          </Button>
        </Paper>
      </Box>
    </Container>
  );
}

export default Home; 