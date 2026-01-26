/**
 * 书签相关的 TanStack Query Hooks
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { bookmarksApi } from '@/lib/api'

// ==================== Query Keys ====================
export const bookmarkKeys = {
  all: ['bookmarks'] as const,
  lists: () => [...bookmarkKeys.all, 'list'] as const,
  list: (category?: string) => [...bookmarkKeys.lists(), { category }] as const,
}

// ==================== Query Hooks ====================

/**
 * 获取书签列表
 * 
 * @example
 * const { data: bookmarks, isLoading } = useBookmarks('security')
 */
export function useBookmarks(category?: string) {
  return useQuery({
    queryKey: bookmarkKeys.list(category),
    queryFn: () => bookmarksApi.getBookmarks(category).then((res) => res.data),
  })
}

// ==================== Mutation Hooks ====================

/**
 * 创建书签
 */
export function useCreateBookmark() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { title: string; url: string; icon?: string; category?: string }) =>
      bookmarksApi.createBookmark(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: bookmarkKeys.lists() })
    },
  })
}

/**
 * 更新书签
 */
export function useUpdateBookmark() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { title?: string; url?: string; icon?: string; category?: string }
    }) => bookmarksApi.updateBookmark(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: bookmarkKeys.lists() })
    },
  })
}

/**
 * 删除书签
 */
export function useDeleteBookmark() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => bookmarksApi.deleteBookmark(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: bookmarkKeys.lists() })
    },
  })
}

/**
 * 获取 URL Meta 信息
 * 用于自动填充书签标题和图标
 */
export function useUrlMeta() {
  return useMutation({
    mutationFn: (url: string) => bookmarksApi.getUrlMeta(url).then((res) => res.data),
  })
}

