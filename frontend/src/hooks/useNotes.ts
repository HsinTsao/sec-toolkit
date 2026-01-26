/**
 * 笔记相关的 TanStack Query Hooks
 * 
 * 这是一个示例文件，展示如何使用 TanStack Query 管理 API 状态
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notesApi } from '@/lib/api'

// ==================== Query Keys ====================
// 定义查询键，用于缓存管理
export const noteKeys = {
  all: ['notes'] as const,
  lists: () => [...noteKeys.all, 'list'] as const,
  list: (params?: { category_id?: string; tag_id?: string; search?: string }) =>
    [...noteKeys.lists(), params] as const,
  details: () => [...noteKeys.all, 'detail'] as const,
  detail: (id: string) => [...noteKeys.details(), id] as const,
  categories: () => [...noteKeys.all, 'categories'] as const,
  tags: () => [...noteKeys.all, 'tags'] as const,
}

// ==================== Query Hooks ====================

/**
 * 获取笔记列表
 * 
 * @example
 * const { data: notes, isLoading, error } = useNotes({ category_id: 'xxx' })
 */
export function useNotes(params?: { category_id?: string; tag_id?: string; search?: string }) {
  return useQuery({
    queryKey: noteKeys.list(params),
    queryFn: () => notesApi.getNotes(params).then((res) => res.data),
  })
}

/**
 * 获取单个笔记详情
 * 
 * @example
 * const { data: note } = useNote('note-id')
 */
export function useNote(id: string) {
  return useQuery({
    queryKey: noteKeys.detail(id),
    queryFn: () => notesApi.getNote(id).then((res) => res.data),
    enabled: !!id, // 只有 id 存在时才执行查询
  })
}

/**
 * 获取分类列表
 */
export function useNoteCategories() {
  return useQuery({
    queryKey: noteKeys.categories(),
    queryFn: () => notesApi.getCategories().then((res) => res.data),
  })
}

/**
 * 获取标签列表
 */
export function useNoteTags() {
  return useQuery({
    queryKey: noteKeys.tags(),
    queryFn: () => notesApi.getTags().then((res) => res.data),
  })
}

// ==================== Mutation Hooks ====================

/**
 * 创建笔记
 * 
 * @example
 * const createNote = useCreateNote()
 * createNote.mutate({ title: '新笔记', content: '内容' })
 */
export function useCreateNote() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { title: string; content?: string; category_id?: string; tag_ids?: string[] }) =>
      notesApi.createNote(data),
    onSuccess: () => {
      // 创建成功后，使笔记列表缓存失效，触发重新获取
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() })
    },
  })
}

/**
 * 更新笔记
 * 
 * @example
 * const updateNote = useUpdateNote()
 * updateNote.mutate({ id: 'note-id', data: { title: '新标题' } })
 */
export function useUpdateNote() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { title?: string; content?: string; category_id?: string; tag_ids?: string[] }
    }) => notesApi.updateNote(id, data),
    onSuccess: (_, variables) => {
      // 更新成功后，使相关缓存失效
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() })
      queryClient.invalidateQueries({ queryKey: noteKeys.detail(variables.id) })
    },
  })
}

/**
 * 删除笔记
 * 
 * @example
 * const deleteNote = useDeleteNote()
 * deleteNote.mutate('note-id')
 */
export function useDeleteNote() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => notesApi.deleteNote(id),
    onSuccess: () => {
      // 删除成功后，使笔记列表缓存失效
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() })
    },
  })
}

// ==================== 分类和标签 Mutations ====================

/**
 * 创建分类
 */
export function useCreateCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { name: string; parent_id?: string; icon?: string }) =>
      notesApi.createCategory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: noteKeys.categories() })
    },
  })
}

/**
 * 删除分类
 */
export function useDeleteCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => notesApi.deleteCategory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: noteKeys.categories() })
    },
  })
}

/**
 * 创建标签
 */
export function useCreateTag() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { name: string; color?: string }) => notesApi.createTag(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: noteKeys.tags() })
    },
  })
}

/**
 * 删除标签
 */
export function useDeleteTag() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => notesApi.deleteTag(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: noteKeys.tags() })
    },
  })
}

