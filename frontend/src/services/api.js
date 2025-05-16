import axios from 'axios';

// 创建axios实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      // 服务器响应了，但状态码不是2xx
      console.error('API错误:', error.response.data);
      return Promise.reject(error.response.data);
    } else if (error.request) {
      // 请求已发送，但没有收到响应
      console.error('网络错误:', error.request);
      return Promise.reject({ message: '网络错误，请检查您的连接' });
    } else {
      // 请求配置出错
      console.error('请求错误:', error.message);
      return Promise.reject({ message: '请求配置错误' });
    }
  }
);

// 查询API
export const queryAPI = {
  // 发送查询
  sendQuery: (query, topK = 5, filter = null, userId = null) => {
    return api.post('/query', { query, top_k: topK, filter, user_id: userId });
  },

  // 获取相似问题建议
  getSuggestions: (query) => {
    return api.post('/query/suggest', { query });
  },
};

// 文档摄取API
export const ingestAPI = {
  // 上传文件
  uploadDocument: (file, onProgress, metadata = {}) => {
    // 检查参数类型 - 如果第二个参数是对象，则没有传入回调函数
    if (typeof onProgress === 'object' && !(onProgress instanceof Function)) {
      metadata = onProgress;
      onProgress = null;
    }

    // 如果file是FormData对象，直接使用
    let formData;
    if (file instanceof FormData) {
      formData = file;
    } else {
      formData = new FormData();
      formData.append('file', file);
      formData.append('metadata', JSON.stringify(metadata));
    }

    return api.post('/ingest/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: onProgress || undefined
    });
  },

  // 从URL导入
  ingestFromUrl: (url, metadata = {}) => {
    return api.post('/ingest/url', { url, metadata });
  },

  // 获取摄取状态
  getIngestStatus: (documentId) => {
    return api.get(`/ingest/status/${documentId}`);
  },

  // 获取所有文档
  getAllDocuments: () => {
    return api.get('/ingest/documents');
  },

  // 删除文档
  deleteDocument: (documentId) => {
    return api.delete(`/ingest/documents/${documentId}`);
  },
  
  // 下载文档
  downloadDocument: (documentId) => {
    return api.get(`/ingest/documents/${documentId}/download`, {
      responseType: 'blob'
    }).then(response => {
      // 创建blob链接并点击下载
      const url = window.URL.createObjectURL(new Blob([response]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `document-${documentId}.pdf`); // 使用适当的文件名和扩展名
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return true;
    });
  }
};

// 管理API
export const adminAPI = {
  // 获取系统状态
  getSystemStatus: () => {
    return api.get('/admin/status');
  },

  // 执行维护操作
  performMaintenance: (action, options = {}) => {
    return api.post('/admin/maintenance', { action, options });
  },

  // 获取服务状态
  getServicesStatus: () => {
    return api.get('/admin/services');
  },

  // 清除知识库
  clearKnowledgeBase: () => {
    return api.post('/admin/clear');
  },

  // 获取系统统计信息
  getStatistics: () => {
    return api.get('/admin/statistics');
  },
};

// 健康检查API
export const healthAPI = {
  check: () => {
    return axios.get('/health');
  },
};

export default {
  query: queryAPI,
  ingest: ingestAPI,
  admin: adminAPI,
  health: healthAPI,
}; 