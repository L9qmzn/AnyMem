// AI Service API 客户端 - 通过后端代理调用AI服务
import { memoServiceClient } from "@/grpcweb";

export interface IndexMemoRequest {
  memo: any; // Memo 对象
  operation?: "upsert" | "delete";
}

export interface IndexMemoResponse {
  memo_uid: string;
  status: string;
  timestamp: string;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  search_mode?: "text" | "image" | "hybrid";
  min_score?: number;
  creator?: string; // 用户过滤，格式如 "users/1"
}

export interface SearchResult {
  memo_uid: string;
  memo_name: string;
  score: number;
  match_type: string;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  search_mode: string;
  total_results: number;
}

export interface TextChunk {
  doc_id: string;
  content: string;
  content_type: string;
}

export interface ImageInfo {
  doc_id: string;
  filename: string;
  caption: string;
}

export interface MemoIndexDetail {
  text_chunks: TextChunk[];
  images: ImageInfo[];
}

export interface MemoIndexInfo {
  memo_uid: string;
  indexed: boolean;
  text_vectors: number;
  image_vectors: number;
  detail?: MemoIndexDetail;
}

export interface RebuildIndexRequest {
  creator: string;
}

export interface RebuildIndexResponse {
  creator: string;
  status: string;
  total_memos: number;
  timestamp: string;
}

export interface RebuildTaskStatus {
  status: string;
  started_at?: string;
  finished_at?: string;
  total: number;
  completed: number;
  failed: number;
  error?: string;
}

export class AIServiceClient {
  // 索引 Memo - 通过后端代理
  async indexMemo(memo: any): Promise<IndexMemoResponse> {
    const response = await memoServiceClient.indexMemo({
      name: memo.name,
    });

    return {
      memo_uid: response.memoUid,
      status: response.status,
      timestamp: response.timestamp,
    };
  }

  // 删除 Memo 索引 - 通过后端代理
  async deleteMemoIndex(memoName: string): Promise<void> {
    await memoServiceClient.deleteMemoIndex({
      name: memoName,
    });
  }

  // 检查服务健康状态 - 通过后端代理
  async healthCheck(): Promise<boolean> {
    try {
      const response = await memoServiceClient.aiHealthCheck({});
      return response.healthy;
    } catch (error) {
      console.error("AI Service health check failed:", error);
      return false;
    }
  }

  // 语义搜索 - 通过后端代理
  async search(request: SearchRequest): Promise<SearchResponse> {
    const response = await memoServiceClient.aiSearch({
      query: request.query,
      topK: request.top_k || 10,
      searchMode: request.search_mode || "hybrid",
      minScore: request.min_score || 0.5,
      creator: request.creator || "",
    });

    return {
      results: response.results.map((r) => ({
        memo_uid: r.memoUid,
        memo_name: r.memoName,
        score: r.score,
        match_type: r.matchType,
      })),
      query: response.query,
      search_mode: response.searchMode,
      total_results: response.totalResults,
    };
  }

  // 检查 Memo 索引状态 - 通过后端代理
  async getMemoIndexInfo(memoName: string, includeDetail: boolean = false): Promise<MemoIndexInfo | null> {
    try {
      const response = await memoServiceClient.getMemoIndexInfo({
        name: memoName,
        includeDetail: includeDetail,
      });
      const result: MemoIndexInfo = {
        memo_uid: response.memoUid,
        indexed: response.indexed,
        text_vectors: response.textVectors,
        image_vectors: response.imageVectors,
      };

      // Add detail if available
      if (includeDetail && response.detail) {
        result.detail = {
          text_chunks: (response.detail.textChunks || []).map((tc) => ({
            doc_id: tc.docId,
            content: tc.content,
            content_type: tc.contentType,
          })),
          images: (response.detail.images || []).map((img) => ({
            doc_id: img.docId,
            filename: img.filename,
            caption: img.caption,
          })),
        };
      }

      return result;
    } catch {
      return null;
    }
  }

  // 重建用户所有索引 - 通过后端代理
  async rebuildIndex(creator: string): Promise<RebuildIndexResponse> {
    const response = await memoServiceClient.rebuildIndex({
      creator,
    });

    return {
      creator: response.creator,
      status: response.status,
      total_memos: response.totalMemos,
      timestamp: response.timestamp,
    };
  }

  // 获取重建任务状态 - 通过后端代理
  async getRebuildStatus(creator: string): Promise<RebuildTaskStatus | null> {
    try {
      const response = await memoServiceClient.getRebuildStatus({
        creator,
      });
      if (response.status === "not_found") {
        return null;
      }
      return {
        status: response.status,
        started_at: response.startedAt,
        finished_at: response.finishedAt,
        total: response.total,
        completed: response.completed,
        failed: response.failed,
        error: response.error,
      };
    } catch {
      return null;
    }
  }
}

// 导出单例
export const aiServiceClient = new AIServiceClient();

// 索引相关的辅助函数
export async function indexMemoIfEnabled(memo: any, userSetting: any): Promise<void> {
  if (!userSetting?.autoGenerateIndex) {
    return;
  }

  try {
    // 先检查服务是否可用
    const isHealthy = await aiServiceClient.healthCheck();
    if (!isHealthy) {
      console.warn("AI Service is not available, skipping indexing");
      return;
    }

    await aiServiceClient.indexMemo(memo);
    console.log(`Memo ${memo.name} indexed successfully`);
  } catch (error) {
    console.error("Failed to index memo:", error);
    // 不抛出错误，避免影响主流程
  }
}

export async function deleteMemoIndexIfEnabled(memoName: string, userSetting: any): Promise<void> {
  if (!userSetting?.autoGenerateIndex) {
    return;
  }

  try {
    await aiServiceClient.deleteMemoIndex(memoName);
    console.log(`Memo ${memoName} index deleted successfully`);
  } catch (error) {
    console.error("Failed to delete memo index:", error);
    // 不抛出错误，避免影响主流程
  }
}
