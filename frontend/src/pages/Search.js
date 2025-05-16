import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Divider,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  Paper,
  TextField,
  Typography,
  Chip,
  Collapse,
  Autocomplete,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import ClearIcon from '@mui/icons-material/Clear';
import HistoryIcon from '@mui/icons-material/History';
import ReactMarkdown from 'react-markdown';

import { queryAPI } from '../services/api';

function Search({ showNotification }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [expandedSources, setExpandedSources] = useState({});
  const [searchHistory, setSearchHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // 从本地存储加载搜索历史
  useEffect(() => {
    const savedHistory = localStorage.getItem('searchHistory');
    if (savedHistory) {
      try {
        setSearchHistory(JSON.parse(savedHistory));
      } catch (error) {
        console.error('Failed to parse search history:', error);
      }
    }
  }, []);

  // 将搜索历史保存到本地存储
  const saveSearchHistory = (history) => {
    localStorage.setItem('searchHistory', JSON.stringify(history));
  };

  // 获取查询建议
  const fetchSuggestions = async (input) => {
    if (!input || input.length < 2) {
      setSuggestions([]);
      return;
    }

    try {
      const { suggestions } = await queryAPI.getSuggestions(input);
      setSuggestions(suggestions || []);
    } catch (error) {
      console.error('Error fetching suggestions:', error);
      setSuggestions([]);
    }
  };

  // 处理查询输入变化
  const handleQueryChange = (event) => {
    const input = event.target.value;
    setQuery(input);
    fetchSuggestions(input);
  };

  // 清除查询
  const handleClearQuery = () => {
    setQuery('');
    setSuggestions([]);
  };

  // 执行搜索
  const handleSearch = async (searchQuery = query) => {
    if (!searchQuery.trim()) {
      showNotification('请输入查询内容', 'warning');
      return;
    }

    setLoading(true);
    try {
      const response = await queryAPI.sendQuery(searchQuery);
      setResult(response);

      // 添加到搜索历史
      const newHistory = [
        { query: searchQuery, timestamp: new Date().toISOString() },
        ...searchHistory.filter((item) => item.query !== searchQuery),
      ].slice(0, 10); // 只保留最近10条
      
      setSearchHistory(newHistory);
      saveSearchHistory(newHistory);
    } catch (error) {
      showNotification(
        error.message || '查询失败，请稍后再试',
        'error'
      );
    } finally {
      setLoading(false);
    }
  };

  // 切换源显示
  const toggleSource = (id) => {
    setExpandedSources({
      ...expandedSources,
      [id]: !expandedSources[id],
    });
  };

  // 从历史中选择查询
  const selectHistoryItem = (historyQuery) => {
    setQuery(historyQuery);
    handleSearch(historyQuery);
    setShowHistory(false);
  };

  // 清除历史
  const clearHistory = () => {
    setSearchHistory([]);
    saveSearchHistory([]);
    setShowHistory(false);
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          知识检索
        </Typography>
        <Typography variant="body1" paragraph align="center" color="textSecondary">
          询问任何问题，获取基于您知识库的准确回答
        </Typography>

        <Box sx={{ position: 'relative' }}>
          <Autocomplete
            freeSolo
            disableClearable
            options={suggestions}
            inputValue={query}
            onInputChange={(event, newValue) => {
              if (event) setQuery(newValue);
            }}
            renderInput={(params) => (
              <TextField
                {...params}
                fullWidth
                variant="outlined"
                placeholder="输入您的问题..."
                value={query}
                onChange={handleQueryChange}
                sx={{ mb: 2 }}
                InputProps={{
                  ...params.InputProps,
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon color="action" />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <>
                      {query && (
                        <IconButton
                          aria-label="清除查询"
                          onClick={handleClearQuery}
                          edge="end"
                        >
                          <ClearIcon />
                        </IconButton>
                      )}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                }}
              />
            )}
          />

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={() => handleSearch()}
              disabled={loading || !query.trim()}
              startIcon={loading ? <CircularProgress size={20} /> : <SearchIcon />}
            >
              {loading ? '搜索中...' : '搜索'}
            </Button>

            <Box>
              <Chip
                icon={<HistoryIcon />}
                label="搜索历史"
                clickable
                color={showHistory ? 'primary' : 'default'}
                onClick={() => setShowHistory(!showHistory)}
                sx={{ mr: 1 }}
              />
            </Box>
          </Box>

          <Collapse in={showHistory}>
            <Paper sx={{ mb: 3, p: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle1">最近的搜索</Typography>
                <Button size="small" onClick={clearHistory} disabled={searchHistory.length === 0}>
                  清除历史
                </Button>
              </Box>
              <Divider sx={{ mb: 1 }} />
              {searchHistory.length === 0 ? (
                <Typography variant="body2" color="textSecondary" align="center">
                  无搜索历史
                </Typography>
              ) : (
                <List dense>
                  {searchHistory.map((item, index) => (
                    <ListItem 
                      key={index} 
                      button 
                      onClick={() => selectHistoryItem(item.query)}
                      sx={{ py: 0.5 }}
                    >
                      <Typography variant="body2" noWrap sx={{ flexGrow: 1 }}>
                        {item.query}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {new Date(item.timestamp).toLocaleString()}
                      </Typography>
                    </ListItem>
                  ))}
                </List>
              )}
            </Paper>
          </Collapse>
        </Box>

        {result && (
          <Card sx={{ mt: 4 }}>
            <CardContent>
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  答案
                </Typography>
                <Box sx={{ backgroundColor: 'background.default', p: 2, borderRadius: 1 }}>
                  <ReactMarkdown>{result.answer}</ReactMarkdown>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                  <Typography variant="caption" color="textSecondary">
                    处理时间: {result.processing_time.toFixed(2)}秒
                  </Typography>
                </Box>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Typography variant="h6" gutterBottom>
                信息来源 ({result.sources.length})
              </Typography>
              <List>
                {result.sources.map((source, index) => (
                  <React.Fragment key={source.document_id}>
                    <ListItem
                      sx={{ 
                        backgroundColor: 'background.default', 
                        borderRadius: 1, 
                        mb: 1,
                        flexDirection: 'column',
                        alignItems: 'stretch'
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                        <Typography variant="subtitle1">
                          {index + 1}. {source.document_name}
                        </Typography>
                        <Box>
                          <Chip
                            size="small"
                            label={`相关性: ${(source.score * 100).toFixed(0)}%`}
                            color={source.score > 0.8 ? 'success' : 'primary'}
                          />
                          <IconButton 
                            size="small" 
                            onClick={() => toggleSource(source.document_id)}
                            sx={{ ml: 1 }}
                          >
                            {expandedSources[source.document_id] ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                          </IconButton>
                        </Box>
                      </Box>

                      <Collapse in={expandedSources[source.document_id] || false} sx={{ width: '100%' }}>
                        <Box sx={{ mt: 1, p: 1, backgroundColor: 'background.paper', borderRadius: 1 }}>
                          <Typography variant="body2">{source.text}</Typography>
                        </Box>
                        {source.metadata && Object.keys(source.metadata).length > 0 && (
                          <Box sx={{ mt: 1 }}>
                            <Typography variant="caption" color="textSecondary">
                              元数据:
                            </Typography>
                            {Object.entries(source.metadata).map(([key, value]) => {
                              if (key !== 'score') { // 已经显示了分数
                                return (
                                  <Chip
                                    key={key}
                                    size="small"
                                    label={`${key}: ${value}`}
                                    sx={{ m: 0.5 }}
                                  />
                                );
                              }
                              return null;
                            })}
                          </Box>
                        )}
                      </Collapse>
                    </ListItem>
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>
        )}
      </Box>
    </Container>
  );
}

export default Search; 