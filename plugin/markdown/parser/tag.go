package parser

import (
	"unicode"
	"unicode/utf8"

	gast "github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/parser"
	"github.com/yuin/goldmark/text"

	mast "github.com/usememos/memos/plugin/markdown/ast"
)

type tagParser struct{}

// decodeRune decodes the first rune from a byte slice and returns it with its size.
// Returns (0, 0) if the slice is empty or contains invalid UTF-8.
func decodeRune(b []byte) (rune, int) {
	if len(b) == 0 {
		return 0, 0
	}

	// Decode UTF-8
	r, size := utf8.DecodeRune(b)
	if r == utf8.RuneError && size == 1 {
		// Invalid UTF-8
		return 0, 0
	}
	return r, size
}

// NewTagParser creates a new inline parser for #tag syntax.
func NewTagParser() parser.InlineParser {
	return &tagParser{}
}

// Trigger returns the characters that trigger this parser.
func (*tagParser) Trigger() []byte {
	return []byte{'#'}
}

// Parse parses #tag syntax.
func (*tagParser) Parse(_ gast.Node, block text.Reader, _ parser.Context) gast.Node {
	line, _ := block.PeekLine()

	// Must start with #
	if len(line) == 0 || line[0] != '#' {
		return nil
	}

	// Check if it's a heading (## or space after #)
	if len(line) > 1 {
		if line[1] == '#' {
			// It's a heading (##), not a tag
			return nil
		}
		if line[1] == ' ' {
			// Space after # - heading or just a hash
			return nil
		}
	} else {
		// Just a lone #
		return nil
	}

	// Scan tag characters
	// Valid: Unicode letters, numbers, dash, underscore, forward slash
	tagEnd := 1 // Start after #
	for tagEnd < len(line) {
		// Convert byte sequence to rune for Unicode support
		r, size := decodeRune(line[tagEnd:])
		if size == 0 {
			break
		}

		// Check if character is valid for tags
		// Valid: Unicode letters, numbers, dash, underscore, forward slash
		isValid := unicode.IsLetter(r) ||
			unicode.IsNumber(r) ||
			r == '-' || r == '_' || r == '/'

		if !isValid {
			break
		}

		tagEnd += size
	}

	// Must have at least one character after #
	if tagEnd == 1 {
		return nil
	}

	// Extract tag (without #)
	tagName := line[1:tagEnd]

	// Make a copy of the tag name
	tagCopy := make([]byte, len(tagName))
	copy(tagCopy, tagName)

	// Advance reader
	block.Advance(tagEnd)

	// Create node
	node := &mast.TagNode{
		Tag: tagCopy,
	}

	return node
}
