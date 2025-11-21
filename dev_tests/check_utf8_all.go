//go:build ignore
// +build ignore

// check_utf8_all.go - Check and fix ALL fields for invalid UTF-8
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"log"
	"unicode/utf8"

	_ "modernc.org/sqlite"
)

var (
	dbPath = flag.String("db", "memos_dev.db", "Database file path")
	fix    = flag.Bool("fix", false, "Fix invalid UTF-8 (default is dry-run)")
)

func main() {
	flag.Parse()

	db, err := sql.Open("sqlite", *dbPath)
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	log.Printf("Checking database: %s", *dbPath)
	log.Printf("Fix mode: %v\n", *fix)

	ctx := context.Background()
	checkAllTables(ctx, db)
}

func checkAllTables(ctx context.Context, db *sql.DB) {
	// Check memo table - all text columns
	log.Println("\n=== Checking MEMO table ===")
	checkMemoTable(ctx, db)

	// Check other tables
	log.Println("\n=== Checking ATTACHMENT table ===")
	checkAttachmentTable(ctx, db)

	log.Println("\n=== Checking REACTION table ===")
	checkReactionTable(ctx, db)

	log.Println("\n=== Checking ACTIVITY table ===")
	checkActivityTable(ctx, db)
}

func checkMemoTable(ctx context.Context, db *sql.DB) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, uid, content, COALESCE(payload, ''), COALESCE(snippet, '')
		FROM memo
	`)
	if err != nil {
		log.Printf("ERROR querying memo table: %v", err)
		return
	}
	defer rows.Close()

	total := 0
	invalid := 0

	for rows.Next() {
		var id int
		var uid, content, payload, snippet string

		if err := rows.Scan(&id, &uid, &content, &payload, &snippet); err != nil {
			log.Printf("ERROR scanning row: %v", err)
			continue
		}

		total++
		hasIssue := false

		// Check content
		if !utf8.ValidString(content) {
			log.Printf("❌ Memo ID=%d UID=%s: Invalid UTF-8 in CONTENT", id, uid)
			hasIssue = true

			if *fix {
				content = sanitizeUTF8(content)
				if _, err := db.ExecContext(ctx, "UPDATE memo SET content = ? WHERE id = ?", content, id); err != nil {
					log.Printf("   ERROR fixing content: %v", err)
				} else {
					log.Printf("   ✓ Fixed content")
				}
			}
		}

		// Check snippet
		if snippet != "" && !utf8.ValidString(snippet) {
			log.Printf("❌ Memo ID=%d UID=%s: Invalid UTF-8 in SNIPPET", id, uid)
			hasIssue = true

			if *fix {
				snippet = sanitizeUTF8(snippet)
				if _, err := db.ExecContext(ctx, "UPDATE memo SET snippet = ? WHERE id = ?", snippet, id); err != nil {
					log.Printf("   ERROR fixing snippet: %v", err)
				} else {
					log.Printf("   ✓ Fixed snippet")
				}
			}
		}

		// Check payload (JSON field)
		if payload != "" {
			if !utf8.ValidString(payload) {
				log.Printf("❌ Memo ID=%d UID=%s: Invalid UTF-8 in PAYLOAD (raw)", id, uid)
				hasIssue = true

				if *fix {
					payload = sanitizeUTF8(payload)
					if _, err := db.ExecContext(ctx, "UPDATE memo SET payload = ? WHERE id = ?", payload, id); err != nil {
						log.Printf("   ERROR fixing payload: %v", err)
					} else {
						log.Printf("   ✓ Fixed payload")
					}
				}
			}

			// Also validate JSON structure
			var payloadMap map[string]interface{}
			if err := json.Unmarshal([]byte(payload), &payloadMap); err != nil {
				log.Printf("⚠️  Memo ID=%d UID=%s: Invalid JSON in payload: %v", id, uid, err)
			} else {
				// Check tags array
				if tags, ok := payloadMap["tags"].([]interface{}); ok {
					for _, tag := range tags {
						if tagStr, ok := tag.(string); ok {
							if !utf8.ValidString(tagStr) {
								log.Printf("❌ Memo ID=%d UID=%s: Invalid UTF-8 in TAG: %s", id, uid, tagStr)
								hasIssue = true
							}
						}
					}
				}
			}
		}

		if hasIssue {
			invalid++
		}
	}

	log.Printf("\nMEMO Summary: %d total, %d with issues", total, invalid)
}

func checkAttachmentTable(ctx context.Context, db *sql.DB) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, name, external_link, type, size
		FROM attachment
	`)
	if err != nil {
		log.Printf("ERROR querying attachment table: %v", err)
		return
	}
	defer rows.Close()

	total := 0
	invalid := 0

	for rows.Next() {
		var id int
		var name, externalLink, atype string
		var size int

		if err := rows.Scan(&id, &name, &externalLink, &atype, &size); err != nil {
			log.Printf("ERROR scanning attachment: %v", err)
			continue
		}

		total++

		if !utf8.ValidString(name) {
			log.Printf("❌ Attachment ID=%d: Invalid UTF-8 in NAME", id)
			invalid++
		}

		if !utf8.ValidString(externalLink) {
			log.Printf("❌ Attachment ID=%d: Invalid UTF-8 in EXTERNAL_LINK", id)
			invalid++
		}

		if !utf8.ValidString(atype) {
			log.Printf("❌ Attachment ID=%d: Invalid UTF-8 in TYPE", id)
			invalid++
		}
	}

	log.Printf("ATTACHMENT Summary: %d total, %d with issues", total, invalid)
}

func checkReactionTable(ctx context.Context, db *sql.DB) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, content_id, reaction_type
		FROM reaction
	`)
	if err != nil {
		log.Printf("ERROR querying reaction table: %v", err)
		return
	}
	defer rows.Close()

	total := 0
	invalid := 0

	for rows.Next() {
		var id int
		var contentID, reactionType string

		if err := rows.Scan(&id, &contentID, &reactionType); err != nil {
			log.Printf("ERROR scanning reaction: %v", err)
			continue
		}

		total++

		if !utf8.ValidString(reactionType) {
			log.Printf("❌ Reaction ID=%d: Invalid UTF-8 in REACTION_TYPE: %s", id, reactionType)
			invalid++
		}
	}

	log.Printf("REACTION Summary: %d total, %d with issues", total, invalid)
}

func checkActivityTable(ctx context.Context, db *sql.DB) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, COALESCE(payload, '')
		FROM activity
	`)
	if err != nil {
		log.Printf("ERROR querying activity table: %v", err)
		return
	}
	defer rows.Close()

	total := 0
	invalid := 0

	for rows.Next() {
		var id int
		var payload string

		if err := rows.Scan(&id, &payload); err != nil {
			log.Printf("ERROR scanning activity: %v", err)
			continue
		}

		total++

		if payload != "" && !utf8.ValidString(payload) {
			log.Printf("❌ Activity ID=%d: Invalid UTF-8 in PAYLOAD", id)
			invalid++
		}
	}

	log.Printf("ACTIVITY Summary: %d total, %d with issues", total, invalid)
}

func sanitizeUTF8(s string) string {
	if utf8.ValidString(s) {
		return s
	}

	result := make([]byte, 0, len(s))
	for len(s) > 0 {
		r, size := utf8.DecodeRuneInString(s)
		if r == utf8.RuneError && size == 1 {
			result = append(result, []byte(string(utf8.RuneError))...)
		} else {
			result = append(result, s[:size]...)
		}
		s = s[size:]
	}
	return string(result)
}
