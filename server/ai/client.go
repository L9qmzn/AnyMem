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

// NewClient creates a new AI service client.
func NewClient() *Client {
	baseURL := os.Getenv("AI_SERVICE_URL")
	if baseURL == "" {
		baseURL = "http://127.0.0.1:8001"
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
