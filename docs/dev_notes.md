# 开发笔记

## 2025-05-17 修复

### 文档删除功能错误修复

修复了删除文档时出现的 `'list' object has no attribute 'tolist'` 错误。

**问题原因**：
- 在 `ingest_service.py` 中的 `delete_document` 方法使用了 Python 列表作为查询向量
- `vector_store.py` 中的 `similarity_search` 方法期望接收 numpy 数组，因为它需要调用 `.tolist()` 方法

**修复方法**：
- 将查询向量从 Python 列表 `[0.0] * self.vector_store.embedding_dimension` 改为 numpy 数组 `np.zeros(self.vector_store.embedding_dimension)`

**相关文件**：
- `app/core/ingest/ingest_service.py`

**测试确认**：
- 文档删除功能现在可以正常工作 