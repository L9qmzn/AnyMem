package v1

import (
	"context"
	"encoding/base64"
	"fmt"
	"net/url"
	"time"

	"google.golang.org/grpc/codes"
	grpcstatus "google.golang.org/grpc/status"

	v1pb "github.com/usememos/memos/proto/gen/api/v1"
	storepb "github.com/usememos/memos/proto/gen/store"
	"github.com/usememos/memos/server/ai"
	"github.com/usememos/memos/store"
)

func (s *APIV1Service) GenerateAiTags(ctx context.Context, request *v1pb.GenerateAiTagsRequest) (*v1pb.GenerateAiTagsResponse, error) {
	memoUID, err := ExtractMemoUIDFromName(request.Name)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.InvalidArgument, "invalid memo name: %v", err)
	}

	memo, err := s.Store.GetMemo(ctx, &store.FindMemo{UID: &memoUID})
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get memo: %v", err)
	}
	if memo == nil {
		return nil, grpcstatus.Errorf(codes.NotFound, "memo not found")
	}

	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	// Get all user's tags by listing their memos
	normalStatus := store.Normal
	userMemos, err := s.Store.ListMemos(ctx, &store.FindMemo{
		CreatorID:       &user.ID,
		RowStatus:       &normalStatus,
		ExcludeComments: true,
		ExcludeContent:  true,
	})
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to list user memos: %v", err)
	}

	// Collect all unique tags from user's memos (including both manual tags and AI tags)
	tagSet := make(map[string]bool)
	for _, m := range userMemos {
		if m.Payload != nil {
			// Add manual tags
			for _, tag := range m.Payload.Tags {
				tagSet[tag] = true
			}
			// Add AI-generated tags
			for _, tag := range m.Payload.AiTags {
				tagSet[tag] = true
			}
		}
	}
	userAllTags := make([]string, 0, len(tagSet))
	for tag := range tagSet {
		userAllTags = append(userAllTags, tag)
	}

	// Get attachments
	attachments, err := s.Store.ListAttachments(ctx, &store.FindAttachment{
		MemoID: &memo.ID,
	})
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to list attachments: %v", err)
	}

	// Build AI request
	aiReq := &ai.TagGenerationRequest{
		UserAllTags: userAllTags,
		MaxTags:     5,
	}
	aiReq.Memo.Name = memo.UID
	aiReq.Memo.Content = memo.Content
	// Ensure tags is always a list (never null)
	aiReq.Memo.Tags = []string{}
	if memo.Payload != nil && memo.Payload.Tags != nil {
		aiReq.Memo.Tags = memo.Payload.Tags
	}

	// Convert attachments to AI format
	aiReq.Memo.Attachments = make([]ai.AttachmentForAI, 0, len(attachments))
	for _, att := range attachments {
		attForAI := ai.AttachmentForAI{
			Name:     att.UID,
			Filename: att.Filename,
			Type:     att.Type,
		}

		// Use presigned URL for S3 and external links
		if att.StorageType == storepb.AttachmentStorageType_S3 || att.StorageType == storepb.AttachmentStorageType_EXTERNAL {
			attForAI.ExternalLink = att.Reference
		} else {
			// For local/database storage, use base64 data URL (OpenAI can't access localhost)
			// Get blob from attachment
			fullAtt, err := s.Store.GetAttachment(ctx, &store.FindAttachment{
				ID:      &att.ID,
				GetBlob: true,
			})
			if err != nil {
				return nil, grpcstatus.Errorf(codes.Internal, "failed to get attachment blob: %v", err)
			}

			blob, err := s.GetAttachmentBlob(fullAtt)
			if err != nil {
				return nil, grpcstatus.Errorf(codes.Internal, "failed to read attachment blob: %v", err)
			}

			// Convert to base64 data URL
			attForAI.ExternalLink = fmt.Sprintf("data:%s;base64,%s", att.Type, base64.StdEncoding.EncodeToString(blob))
		}

		aiReq.Memo.Attachments = append(aiReq.Memo.Attachments, attForAI)
	}

	// Get AI service URL from instance settings
	aiSetting, err := s.Store.GetInstanceAiSetting(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI settings: %v", err)
	}

	// Call AI service
	aiClient := ai.NewClient(aiSetting.AiServiceUrl)
	aiResp, err := aiClient.GenerateTags(ctx, aiReq)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to generate AI tags: %v", err)
	}

	return &v1pb.GenerateAiTagsResponse{
		Tags: aiResp.Tags,
	}, nil
}

// getAIClient creates an AI client with the configured service URL.
func (s *APIV1Service) getAIClient(ctx context.Context) (*ai.Client, error) {
	aiSetting, err := s.Store.GetInstanceAiSetting(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get AI settings: %w", err)
	}
	return ai.NewClient(aiSetting.AiServiceUrl), nil
}

// IndexMemo indexes a memo for AI search.
func (s *APIV1Service) IndexMemo(ctx context.Context, request *v1pb.IndexMemoRequest) (*v1pb.IndexMemoResponse, error) {
	memoUID, err := ExtractMemoUIDFromName(request.Name)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.InvalidArgument, "invalid memo name: %v", err)
	}

	memo, err := s.Store.GetMemo(ctx, &store.FindMemo{UID: &memoUID})
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get memo: %v", err)
	}
	if memo == nil {
		return nil, grpcstatus.Errorf(codes.NotFound, "memo not found")
	}

	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	// Check if user owns the memo or is admin
	if memo.CreatorID != user.ID && user.Role != store.RoleHost && user.Role != store.RoleAdmin {
		return nil, grpcstatus.Errorf(codes.PermissionDenied, "permission denied")
	}

	// Get attachments
	attachments, err := s.Store.ListAttachments(ctx, &store.FindAttachment{
		MemoID: &memo.ID,
	})
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to list attachments: %v", err)
	}

	// Convert memo to the format expected by AI service
	memoForAI := s.convertMemoForAI(ctx, memo, attachments)

	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI client: %v", err)
	}

	resp, err := aiClient.IndexMemo(ctx, memoForAI)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to index memo: %v", err)
	}

	return &v1pb.IndexMemoResponse{
		MemoUid:   resp.MemoUID,
		Status:    resp.Status,
		Timestamp: resp.Timestamp,
	}, nil
}

// convertMemoForAI converts a memo to the format expected by the AI service.
func (s *APIV1Service) convertMemoForAI(ctx context.Context, memo *store.Memo, attachments []*store.Attachment) map[string]interface{} {
	// Build attachments list
	attList := make([]map[string]interface{}, 0, len(attachments))
	for _, att := range attachments {
		attForAI := map[string]interface{}{
			"name":     att.UID,
			"filename": att.Filename,
			"type":     att.Type,
		}

		// Use presigned URL for S3 and external links
		if att.StorageType == storepb.AttachmentStorageType_S3 || att.StorageType == storepb.AttachmentStorageType_EXTERNAL {
			attForAI["externalLink"] = att.Reference
		} else {
			// For local/database storage, use base64 data URL
			fullAtt, err := s.Store.GetAttachment(ctx, &store.FindAttachment{
				ID:      &att.ID,
				GetBlob: true,
			})
			if err == nil && fullAtt != nil {
				blob, err := s.GetAttachmentBlob(fullAtt)
				if err == nil {
					attForAI["externalLink"] = fmt.Sprintf("data:%s;base64,%s", att.Type, base64.StdEncoding.EncodeToString(blob))
				}
			}
		}

		attList = append(attList, attForAI)
	}

	// Get tags
	tags := []string{}
	aiTags := []string{}
	if memo.Payload != nil {
		if memo.Payload.Tags != nil {
			tags = memo.Payload.Tags
		}
		if memo.Payload.AiTags != nil {
			aiTags = memo.Payload.AiTags
		}
	}

	return map[string]interface{}{
		"name":        fmt.Sprintf("memos/%s", memo.UID),
		"uid":         memo.UID,
		"content":     memo.Content,
		"creator":     fmt.Sprintf("users/%d", memo.CreatorID),
		"createTime":  time.Unix(memo.CreatedTs, 0).Format(time.RFC3339),
		"updateTime":  time.Unix(memo.UpdatedTs, 0).Format(time.RFC3339),
		"displayTime": time.Unix(memo.CreatedTs, 0).Format(time.RFC3339),
		"tags":        tags,
		"aiTags":      aiTags,
		"attachments": attList,
	}
}

// DeleteMemoIndex deletes the index of a memo.
func (s *APIV1Service) DeleteMemoIndex(ctx context.Context, request *v1pb.DeleteMemoIndexRequest) (*v1pb.DeleteMemoIndexResponse, error) {
	memoUID, err := ExtractMemoUIDFromName(request.Name)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.InvalidArgument, "invalid memo name: %v", err)
	}

	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI client: %v", err)
	}

	err = aiClient.DeleteMemoIndex(ctx, memoUID)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to delete memo index: %v", err)
	}

	return &v1pb.DeleteMemoIndexResponse{
		Success: true,
	}, nil
}

// GetMemoIndexInfo gets the index info of a memo.
func (s *APIV1Service) GetMemoIndexInfo(ctx context.Context, request *v1pb.GetMemoIndexInfoRequest) (*v1pb.MemoIndexInfo, error) {
	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI client: %v", err)
	}

	info, err := aiClient.GetMemoIndexInfo(ctx, request.Name, request.IncludeDetail)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get memo index info: %v", err)
	}
	if info == nil {
		return &v1pb.MemoIndexInfo{
			MemoUid: request.Name,
			Indexed: false,
		}, nil
	}

	result := &v1pb.MemoIndexInfo{
		MemoUid:      info.MemoUID,
		Indexed:      info.Indexed,
		TextVectors:  int32(info.TextCount),
		ImageVectors: int32(info.ImageCount),
	}

	// Add detail if requested and available
	if request.IncludeDetail && info.Detail != nil {
		detail := &v1pb.MemoIndexDetail{
			TextChunks: make([]*v1pb.TextChunk, 0, len(info.Detail.TextChunks)),
			Images:     make([]*v1pb.ImageInfo, 0, len(info.Detail.Images)),
		}

		for _, tc := range info.Detail.TextChunks {
			detail.TextChunks = append(detail.TextChunks, &v1pb.TextChunk{
				DocId:       tc.DocID,
				Content:     tc.Content,
				ContentType: tc.ContentType,
			})
		}

		for _, img := range info.Detail.Images {
			detail.Images = append(detail.Images, &v1pb.ImageInfo{
				DocId:    img.DocID,
				Filename: img.Filename,
				Caption:  img.Caption,
			})
		}

		result.Detail = detail
	}

	return result, nil
}

// AiSearch performs AI semantic search on memos.
func (s *APIV1Service) AiSearch(ctx context.Context, request *v1pb.AiSearchRequest) (*v1pb.AiSearchResponse, error) {
	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI client: %v", err)
	}

	// Use current user as creator if not specified
	creator := request.Creator
	if creator == "" {
		creator = fmt.Sprintf("users/%d", user.ID)
	}

	searchReq := &ai.SearchRequest{
		Query:      request.Query,
		TopK:       int(request.TopK),
		SearchMode: request.SearchMode,
		MinScore:   request.MinScore,
		Creator:    creator,
	}

	resp, err := aiClient.Search(ctx, searchReq)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to search: %v", err)
	}

	results := make([]*v1pb.AiSearchResult, 0, len(resp.Results))
	for _, r := range resp.Results {
		results = append(results, &v1pb.AiSearchResult{
			MemoUid:   r.MemoUID,
			MemoName:  r.MemoName,
			Score:     r.Score,
			MatchType: r.MatchType,
		})
	}

	return &v1pb.AiSearchResponse{
		Results:      results,
		Query:        resp.Query,
		SearchMode:   resp.SearchMode,
		TotalResults: int32(resp.TotalResults),
	}, nil
}

// RebuildIndex rebuilds all memo indexes for a user.
func (s *APIV1Service) RebuildIndex(ctx context.Context, request *v1pb.RebuildIndexRequest) (*v1pb.RebuildIndexResponse, error) {
	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI client: %v", err)
	}

	resp, err := aiClient.RebuildIndex(ctx, request.Creator)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to rebuild index: %v", err)
	}

	return &v1pb.RebuildIndexResponse{
		Creator:    resp.Creator,
		Status:     resp.Status,
		TotalMemos: int32(resp.TotalMemos),
		Timestamp:  resp.Timestamp,
	}, nil
}

// GetRebuildStatus gets the rebuild index task status.
func (s *APIV1Service) GetRebuildStatus(ctx context.Context, request *v1pb.GetRebuildStatusRequest) (*v1pb.RebuildTaskStatus, error) {
	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, grpcstatus.Errorf(codes.Unauthenticated, "user not authenticated")
	}

	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get AI client: %v", err)
	}

	// URL encode the creator parameter
	creator := url.PathEscape(request.Creator)

	taskStatus, err := aiClient.GetRebuildStatus(ctx, creator)
	if err != nil {
		return nil, grpcstatus.Errorf(codes.Internal, "failed to get rebuild status: %v", err)
	}
	if taskStatus == nil {
		return &v1pb.RebuildTaskStatus{
			Status: "not_found",
		}, nil
	}

	return &v1pb.RebuildTaskStatus{
		Status:     taskStatus.Status,
		StartedAt:  taskStatus.StartedAt,
		FinishedAt: taskStatus.FinishedAt,
		Total:      int32(taskStatus.Total),
		Completed:  int32(taskStatus.Completed),
		Failed:     int32(taskStatus.Failed),
		Error:      taskStatus.Error,
	}, nil
}

// AiHealthCheck checks the AI service health.
func (s *APIV1Service) AiHealthCheck(ctx context.Context, request *v1pb.AiHealthCheckRequest) (*v1pb.AiHealthCheckResponse, error) {
	aiClient, err := s.getAIClient(ctx)
	if err != nil {
		return &v1pb.AiHealthCheckResponse{
			Healthy: false,
		}, nil
	}

	healthy, _ := aiClient.HealthCheck(ctx)
	return &v1pb.AiHealthCheckResponse{
		Healthy: healthy,
	}, nil
}
