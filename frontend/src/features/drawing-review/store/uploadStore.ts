import { create } from 'zustand'
import { processSinglePdf, uploadPdfs } from '../api/drawingApi'

export type UploadRunStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'failed'

interface UploadState {
  files: File[]
  status: UploadRunStatus
  taskId: string | null
  currentFileIndex: number
  currentFileName: string
  errorMessage: string | null
  addFiles: (files: File[]) => void
  removeFile: (index: number) => void
  clearFiles: () => void
  resetRun: () => void
  run: () => Promise<string | null>
}

const uniqueFiles = (existing: File[], incoming: File[]): File[] => {
  const known = new Set(existing.map((file) => `${file.name}:${file.size}:${file.lastModified}`))
  return [...existing, ...incoming.filter((file) => {
    const key = `${file.name}:${file.size}:${file.lastModified}`
    if (known.has(key)) return false
    known.add(key)
    return true
  })]
}

export const useUploadStore = create<UploadState>((set, get) => ({
  files: [],
  status: 'idle',
  taskId: null,
  currentFileIndex: 0,
  currentFileName: '',
  errorMessage: null,
  addFiles: (files) => set((state) => ({ files: uniqueFiles(state.files, files) })),
  removeFile: (index) => set((state) => ({ files: state.files.filter((_, itemIndex) => itemIndex !== index) })),
  clearFiles: () => set({ files: [] }),
  resetRun: () => set({ status: 'idle', taskId: null, currentFileIndex: 0, currentFileName: '', errorMessage: null }),
  run: async () => {
    const files = get().files
    if (!files.length || get().status === 'uploading' || get().status === 'processing') return null

    set({ status: 'uploading', taskId: null, currentFileIndex: 0, currentFileName: '', errorMessage: null })
    try {
      const upload = await uploadPdfs(files)
      const taskId = upload.task_id
      const fileNames = upload.file_names.length ? upload.file_names : files.map((file) => file.name)
      set({ status: 'processing', taskId })

      for (let index = 0; index < files.length; index += 1) {
        set({ currentFileIndex: index + 1, currentFileName: fileNames[index] || files[index].name })
        await processSinglePdf(taskId, index + 1)
      }

      set({ status: 'completed', currentFileIndex: files.length })
      return taskId
    } catch (error) {
      const message = error instanceof Error ? error.message : '任务处理失败，请查看已有结果或重新创建任务。'
      set({ status: 'failed', errorMessage: message })
      return null
    }
  },
}))
