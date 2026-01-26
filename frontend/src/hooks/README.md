# API Hooks 使用指南

本项目使用 **TanStack Query** 管理 API 状态，结合 **OpenAPI 自动生成** 确保类型安全。

## 快速开始

### 1. 生成 API 客户端（可选但推荐）

确保后端服务正在运行，然后执行：

```bash
npm run generate-api
```

这会从后端的 OpenAPI 规范自动生成类型安全的 API 客户端。

### 2. 使用 Query Hooks

```tsx
import { useNotes, useCreateNote, useDeleteNote } from '@/hooks'

function NotesPage() {
  // 获取数据 - 自动管理 loading、error、缓存
  const { data: notes, isLoading, error } = useNotes()
  
  // 创建操作
  const createNote = useCreateNote()
  
  // 删除操作
  const deleteNote = useDeleteNote()

  if (isLoading) return <div>加载中...</div>
  if (error) return <div>出错了: {error.message}</div>

  return (
    <div>
      <button 
        onClick={() => createNote.mutate({ title: '新笔记' })}
        disabled={createNote.isPending}
      >
        {createNote.isPending ? '创建中...' : '创建笔记'}
      </button>
      
      {notes?.map(note => (
        <div key={note.id}>
          <span>{note.title}</span>
          <button 
            onClick={() => deleteNote.mutate(note.id)}
            disabled={deleteNote.isPending}
          >
            删除
          </button>
        </div>
      ))}
    </div>
  )
}
```

## Hooks 列表

### 笔记 (useNotes.ts)

| Hook | 描述 |
|------|------|
| `useNotes(params?)` | 获取笔记列表 |
| `useNote(id)` | 获取单个笔记 |
| `useNoteCategories()` | 获取分类列表 |
| `useNoteTags()` | 获取标签列表 |
| `useCreateNote()` | 创建笔记 |
| `useUpdateNote()` | 更新笔记 |
| `useDeleteNote()` | 删除笔记 |
| `useCreateCategory()` | 创建分类 |
| `useDeleteCategory()` | 删除分类 |
| `useCreateTag()` | 创建标签 |
| `useDeleteTag()` | 删除标签 |

### 书签 (useBookmarks.ts)

| Hook | 描述 |
|------|------|
| `useBookmarks(category?)` | 获取书签列表 |
| `useCreateBookmark()` | 创建书签 |
| `useUpdateBookmark()` | 更新书签 |
| `useDeleteBookmark()` | 删除书签 |
| `useUrlMeta()` | 获取 URL Meta 信息 |

## Query Keys

每个模块都定义了 Query Keys，用于缓存管理：

```ts
// 笔记相关的 keys
noteKeys.all         // ['notes']
noteKeys.lists()     // ['notes', 'list']
noteKeys.list(params) // ['notes', 'list', params]
noteKeys.detail(id)  // ['notes', 'detail', id]

// 书签相关的 keys
bookmarkKeys.all     // ['bookmarks']
bookmarkKeys.list()  // ['bookmarks', 'list']
```

## 核心优势

1. **自动缓存**: 相同请求使用缓存，避免重复请求
2. **自动重试**: 请求失败自动重试
3. **后台更新**: 返回缓存的同时后台检查更新
4. **请求去重**: 多组件同时请求相同数据只发一次请求
5. **乐观更新**: 可配置立即显示结果
6. **类型安全**: 配合 OpenAPI 生成，全程类型提示

## 添加新的 Hooks

1. 在 `src/hooks/` 下创建新文件，如 `useTools.ts`
2. 定义 Query Keys
3. 创建 Query 和 Mutation Hooks
4. 在 `src/hooks/index.ts` 中导出

