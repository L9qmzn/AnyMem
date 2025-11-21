//go:build ignore
// +build ignore

// fix_utf8.go - Repair invalid UTF-8 sequences in memo database
//
// This script scans all memos in the database and fixes any invalid UTF-8
// sequences that could cause gRPC encoding errors.
//
// Usage:
//   go run fix_utf8.go [--data-dir PATH] [--driver sqlite|mysql|postgres] [--dsn CONNECTION_STRING]
//
// Examples:
//   go run fix_utf8.go
//   go run fix_utf8.go --data-dir ~/.memos
//   go run fix_utf8.go --driver mysql --dsn "user:pass@tcp(localhost:3306)/memos"

package main

import (
	"context"
	"database/sql"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"unicode/utf8"

	_ "github.com/go-sql-driver/mysql"
	_ "github.com/lib/pq"
	_ "modernc.org/sqlite"
)

var (
	dataDir = flag.String("data-dir", "", "Data directory (default: ~/.memos)")
	driver  = flag.String("driver", "sqlite", "Database driver: sqlite, mysql, postgres")
	dsn     = flag.String("dsn", "", "Database connection string (for mysql/postgres)")
	dryRun  = flag.Bool("dry-run", false, "Only check for invalid UTF-8 without fixing")
)

func main() {
	flag.Parse()

	// Set default data directory if not specified
	if *dataDir == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			log.Fatalf("Failed to get home directory: %v", err)
		}
		*dataDir = filepath.Join(home, ".memos")
	}

	// Build connection string
	var connStr string
	switch *driver {
	case "sqlite":
		dbPath := filepath.Join(*dataDir, "memos_prod.db")
		if *dsn != "" {
			dbPath = *dsn
		}
		connStr = dbPath
		log.Printf("Using SQLite database: %s", dbPath)
	case "mysql":
		if *dsn == "" {
			log.Fatal("--dsn is required for MySQL driver")
		}
		connStr = *dsn
		log.Printf("Using MySQL database")
	case "postgres":
		if *dsn == "" {
			log.Fatal("--dsn is required for PostgreSQL driver")
		}
		connStr = *dsn
		log.Printf("Using PostgreSQL database")
	default:
		log.Fatalf("Unknown driver: %s", *driver)
	}

	// Open database
	db, err := sql.Open(*driver, connStr)
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	log.Println("Database connected successfully")

	// Run the fix
	ctx := context.Background()
	if err := fixInvalidUTF8(ctx, db); err != nil {
		log.Fatalf("Failed to fix UTF-8: %v", err)
	}

	log.Println("Done!")
}

func fixInvalidUTF8(ctx context.Context, db *sql.DB) error {
	// Query all memos
	rows, err := db.QueryContext(ctx, "SELECT id, uid, content FROM memo")
	if err != nil {
		return fmt.Errorf("failed to query memos: %w", err)
	}
	defer rows.Close()

	var (
		totalCount   int
		invalidCount int
		fixedCount   int
	)

	for rows.Next() {
		var (
			id      int
			uid     string
			content string
		)

		if err := rows.Scan(&id, &uid, &content); err != nil {
			return fmt.Errorf("failed to scan row: %w", err)
		}

		totalCount++

		// Check if content is valid UTF-8
		if !utf8.ValidString(content) {
			invalidCount++

			log.Printf("Found invalid UTF-8 in memo %s (ID: %d)", uid, id)
			log.Printf("  Content length: %d bytes", len(content))

			if *dryRun {
				log.Printf("  [DRY-RUN] Would sanitize this memo")
				continue
			}

			// Sanitize the content
			sanitized := sanitizeUTF8(content)

			// Update the database
			_, err := db.ExecContext(ctx,
				"UPDATE memo SET content = ? WHERE id = ?",
				sanitized, id,
			)
			if err != nil {
				log.Printf("  ERROR: Failed to update memo: %v", err)
				continue
			}

			fixedCount++
			log.Printf("  ✓ Fixed and saved")
		}
	}

	if err := rows.Err(); err != nil {
		return fmt.Errorf("error iterating rows: %w", err)
	}

	// Print summary
	fmt.Println()
	fmt.Println("=" + "=")
	fmt.Printf("Summary:\n")
	fmt.Printf("  Total memos scanned: %d\n", totalCount)
	fmt.Printf("  Invalid UTF-8 found: %d\n", invalidCount)
	if *dryRun {
		fmt.Printf("  [DRY-RUN] No changes made\n")
	} else {
		fmt.Printf("  Memos fixed: %d\n", fixedCount)
	}
	fmt.Println("=" + "=")

	return nil
}

// sanitizeUTF8 removes invalid UTF-8 sequences from a string.
// Invalid sequences are replaced with the Unicode replacement character (�).
func sanitizeUTF8(s string) string {
	if utf8.ValidString(s) {
		return s
	}

	// String contains invalid UTF-8, need to clean it
	result := make([]byte, 0, len(s))

	for len(s) > 0 {
		r, size := utf8.DecodeRuneInString(s)
		if r == utf8.RuneError && size == 1 {
			// Invalid UTF-8 sequence, replace with replacement character
			result = append(result, []byte(string(utf8.RuneError))...)
		} else {
			result = append(result, s[:size]...)
		}
		s = s[size:]
	}

	return string(result)
}
