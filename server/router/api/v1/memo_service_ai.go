package v1

import (
	"context"
	"encoding/base64"
	"fmt"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	v1pb "github.com/usememos/memos/proto/gen/api/v1"
	storepb "github.com/usememos/memos/proto/gen/store"
	"github.com/usememos/memos/server/ai"
	"github.com/usememos/memos/store"
)

func (s *APIV1Service) GenerateAiTags(ctx context.Context, request *v1pb.GenerateAiTagsRequest) (*v1pb.GenerateAiTagsResponse, error) {
	memoUID, err := ExtractMemoUIDFromName(request.Name)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid memo name: %v", err)
	}

	memo, err := s.Store.GetMemo(ctx, &store.FindMemo{UID: &memoUID})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to get memo: %v", err)
	}
	if memo == nil {
		return nil, status.Errorf(codes.NotFound, "memo not found")
	}

	user, err := s.GetCurrentUser(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to get current user")
	}
	if user == nil {
		return nil, status.Errorf(codes.Unauthenticated, "user not authenticated")
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
		return nil, status.Errorf(codes.Internal, "failed to list user memos: %v", err)
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
		return nil, status.Errorf(codes.Internal, "failed to list attachments: %v", err)
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
				return nil, status.Errorf(codes.Internal, "failed to get attachment blob: %v", err)
			}

			blob, err := s.GetAttachmentBlob(fullAtt)
			if err != nil {
				return nil, status.Errorf(codes.Internal, "failed to read attachment blob: %v", err)
			}

			// Convert to base64 data URL
			attForAI.ExternalLink = fmt.Sprintf("data:%s;base64,%s", att.Type, base64.StdEncoding.EncodeToString(blob))
		}

		aiReq.Memo.Attachments = append(aiReq.Memo.Attachments, attForAI)
	}

	// Call AI service
	aiClient := ai.NewClient()
	aiResp, err := aiClient.GenerateTags(ctx, aiReq)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to generate AI tags: %v", err)
	}

	return &v1pb.GenerateAiTagsResponse{
		Tags: aiResp.Tags,
	}, nil
}
