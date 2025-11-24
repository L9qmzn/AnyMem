// AI Service API 客户端
const AI_SERVICE_BASE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8000";

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

export interface MemoIndexInfo {
  memo_uid: string;
  indexed: boolean;
  text_vectors: number;
  image_vectors: number;
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
  private baseUrl: string;

  constructor(baseUrl: string = AI_SERVICE_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // 索引 Memo
  async indexMemo(memo: any): Promise<IndexMemoResponse> {
    const response = await fetch(`${this.baseUrl}/internal/index/memo`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        memo: memo,
        operation: "upsert",
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to index memo: ${response.statusText}`);
    }

    return response.json();
  }

  // 删除 Memo 索引
  async deleteMemoIndex(memoUid: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/internal/index/memo/${encodeURIComponent(memoUid)}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      throw new Error(`Failed to delete memo index: ${response.statusText}`);
    }
  }

  // 检查服务健康状态
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      console.error("AI Service health check failed:", error);
      return false;
    }
  }

  // 语义搜索
  async search(request: SearchRequest): Promise<SearchResponse> {
    const response = await fetch(`${this.baseUrl}/internal/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: request.query,
        top_k: request.top_k || 10,
        search_mode: request.search_mode || "hybrid",
        min_score: request.min_score || 0.5,
        creator: request.creator, // 用户过滤
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to search: ${response.statusText}`);
    }

    return response.json();
  }

  // 检查 Memo 索引状态
  async getMemoIndexInfo(memoName: string): Promise<MemoIndexInfo | null> {
    try {
      const response = await fetch(`${this.baseUrl}/internal/index/memo/${encodeURIComponent(memoName)}`);
      if (response.status === 404) {
        return { memo_uid: memoName, indexed: false, text_vectors: 0, image_vectors: 0 };
      }
      if (!response.ok) {
        throw new Error(`Failed to get memo index info: ${response.statusText}`);
      }
      const data = await response.json();
      return {
        memo_uid: memoName,
        indexed: true,
        text_vectors: data.text_count || 0,
        image_vectors: data.image_count || 0,
      };
    } catch {
      return null;
    }
  }

  // 重建用户所有索引
  async rebuildIndex(creator: string): Promise<RebuildIndexResponse> {
    const response = await fetch(`${this.baseUrl}/internal/index/rebuild`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ creator }),
    });

    if (!response.ok) {
      throw new Error(`Failed to start rebuild: ${response.statusText}`);
    }

    return response.json();
  }

  // 获取重建任务状态
  async getRebuildStatus(creator: string): Promise<RebuildTaskStatus | null> {
    try {
      const response = await fetch(`${this.baseUrl}/internal/index/rebuild/${encodeURIComponent(creator)}`);
      if (response.status === 404) {
        return null;
      }
      if (!response.ok) {
        throw new Error(`Failed to get rebuild status: ${response.statusText}`);
      }
      return response.json();
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

export async function deleteMemoIndexIfEnabled(memoUid: string, userSetting: any): Promise<void> {
  if (!userSetting?.autoGenerateIndex) {
    return;
  }

  try {
    await aiServiceClient.deleteMemoIndex(memoUid);
    console.log(`Memo ${memoUid} index deleted successfully`);
  } catch (error) {
    console.error("Failed to delete memo index:", error);
    // 不抛出错误，避免影响主流程
  }
}
