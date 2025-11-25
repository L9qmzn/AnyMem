package ai

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// Client is the AI service client.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// DefaultAIServiceURL is the default URL for the AI service.
const DefaultAIServiceURL = "http://127.0.0.1:8000"

// NewClient creates a new AI service client.
// If aiServiceURL is empty, it falls back to AI_SERVICE_URL env var, then to default.
func NewClient(aiServiceURL string) *Client {
	baseURL := aiServiceURL
	if baseURL == "" {
		baseURL = os.Getenv("AI_SERVICE_URL")
	}
	if baseURL == "" {
		baseURL = DefaultAIServiceURL
	}

	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

// TagGenerationRequest is the request for tag generation.
type TagGenerationRequest struct {
	Memo struct {
		Name        string                 `json:"name"`
		Content     string                 `json:"content"`
		Tags        []string               `json:"tags"`
		Attachments []AttachmentForAI `json:"attachments"`
	} `json:"memo"`
	UserAllTags []string `json:"user_all_tags"`
	MaxTags     int      `json:"max_tags"`
}

// AttachmentForAI represents an attachment for AI service.
type AttachmentForAI struct {
	Name         string `json:"name,omitempty"`
	Filename     string `json:"filename,omitempty"`
	Type         string `json:"type,omitempty"`
	ExternalLink string `json:"externalLink,omitempty"`
}

// TagGenerationResponse is the response from tag generation.
type TagGenerationResponse struct {
	Success    bool     `json:"success"`
	Tags       []string `json:"tags"`
	MergedTags []string `json:"merged_tags"`
	Error      string   `json:"error,omitempty"`
}

// GenerateTags generates tags for a memo using AI service.
func (c *Client) GenerateTags(ctx context.Context, req *TagGenerationRequest) (*TagGenerationResponse, error) {
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf("%s/api/v1/tags/generate", c.baseURL),
		bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	var result TagGenerationResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	if !result.Success {
		return nil, fmt.Errorf("AI service error: %s", result.Error)
	}

	return &result, nil
}

// IndexMemoRequest is the request for indexing a memo.
type IndexMemoRequest struct {
	Memo      interface{} `json:"memo"`
	Operation string      `json:"operation"`
}

// IndexMemoResponse is the response from indexing a memo.
type IndexMemoResponse struct {
	MemoUID   string `json:"memo_uid"`
	Status    string `json:"status"`
	Timestamp string `json:"timestamp"`
}

// IndexMemo indexes a memo in the AI service.
func (c *Client) IndexMemo(ctx context.Context, memo interface{}) (*IndexMemoResponse, error) {
	reqBody, err := json.Marshal(&IndexMemoRequest{
		Memo:      memo,
		Operation: "upsert",
	})
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf("%s/internal/index/memo", c.baseURL),
		bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Accept both 200 OK and 202 Accepted (async processing)
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	var result IndexMemoResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &result, nil
}

// DeleteMemoIndex deletes the index of a memo.
func (c *Client) DeleteMemoIndex(ctx context.Context, memoUID string) error {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodDelete,
		fmt.Sprintf("%s/internal/index/memo/%s", c.baseURL, memoUID),
		nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

// MemoIndexInfo is the index info of a memo.
type MemoIndexInfo struct {
	MemoUID      string `json:"memo_uid"`
	Indexed      bool   `json:"indexed"`
	TextCount    int    `json:"text_count"`
	ImageCount   int    `json:"image_count"`
	TextVectors  int    `json:"text_vectors"`
	ImageVectors int    `json:"image_vectors"`
}

// GetMemoIndexInfo gets the index info of a memo.
func (c *Client) GetMemoIndexInfo(ctx context.Context, memoName string) (*MemoIndexInfo, error) {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/internal/index/memo/%s", c.baseURL, memoName),
		nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return &MemoIndexInfo{
			MemoUID: memoName,
			Indexed: false,
		}, nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	var result MemoIndexInfo
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}
	result.Indexed = true

	return &result, nil
}

// SearchRequest is the request for AI search.
type SearchRequest struct {
	Query      string  `json:"query"`
	TopK       int     `json:"top_k"`
	SearchMode string  `json:"search_mode"`
	MinScore   float32 `json:"min_score"`
	Creator    string  `json:"creator"`
}

// SearchResult is a single search result.
type SearchResult struct {
	MemoUID   string  `json:"memo_uid"`
	MemoName  string  `json:"memo_name"`
	Score     float32 `json:"score"`
	MatchType string  `json:"match_type"`
}

// SearchResponse is the response from AI search.
type SearchResponse struct {
	Results      []SearchResult `json:"results"`
	Query        string         `json:"query"`
	SearchMode   string         `json:"search_mode"`
	TotalResults int            `json:"total_results"`
}

// Search performs AI semantic search.
func (c *Client) Search(ctx context.Context, req *SearchRequest) (*SearchResponse, error) {
	if req.TopK == 0 {
		req.TopK = 10
	}
	if req.SearchMode == "" {
		req.SearchMode = "hybrid"
	}
	if req.MinScore == 0 {
		req.MinScore = 0.5
	}

	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf("%s/internal/search", c.baseURL),
		bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	var result SearchResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &result, nil
}

// RebuildIndexRequest is the request to rebuild index.
type RebuildIndexRequest struct {
	Creator string `json:"creator"`
}

// RebuildIndexResponse is the response from rebuild index.
type RebuildIndexResponse struct {
	Creator    string `json:"creator"`
	Status     string `json:"status"`
	TotalMemos int    `json:"total_memos"`
	Timestamp  string `json:"timestamp"`
}

// RebuildIndex starts rebuilding all indexes for a user.
func (c *Client) RebuildIndex(ctx context.Context, creator string) (*RebuildIndexResponse, error) {
	reqBody, err := json.Marshal(&RebuildIndexRequest{Creator: creator})
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf("%s/internal/index/rebuild", c.baseURL),
		bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	var result RebuildIndexResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &result, nil
}

// RebuildTaskStatus is the status of a rebuild task.
type RebuildTaskStatus struct {
	Status     string `json:"status"`
	StartedAt  string `json:"started_at,omitempty"`
	FinishedAt string `json:"finished_at,omitempty"`
	Total      int    `json:"total"`
	Completed  int    `json:"completed"`
	Failed     int    `json:"failed"`
	Error      string `json:"error,omitempty"`
}

// GetRebuildStatus gets the status of a rebuild task.
func (c *Client) GetRebuildStatus(ctx context.Context, creator string) (*RebuildTaskStatus, error) {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/internal/index/rebuild/%s", c.baseURL, creator),
		nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(body))
	}

	var result RebuildTaskStatus
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	return &result, nil
}

// HealthCheck checks if the AI service is healthy.
func (c *Client) HealthCheck(ctx context.Context) (bool, error) {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/health", c.baseURL),
		nil)
	if err != nil {
		return false, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return false, nil // Service is not reachable
	}
	defer resp.Body.Close()

	return resp.StatusCode == http.StatusOK, nil
}
