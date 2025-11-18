package util //nolint:revive // util namespace is intentional for shared helpers

import (
	"crypto/rand"
	"math/big"
	"net/mail"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/google/uuid"
)

// ConvertStringToInt32 converts a string to int32.
func ConvertStringToInt32(src string) (int32, error) {
	parsed, err := strconv.ParseInt(src, 10, 32)
	if err != nil {
		return 0, err
	}
	return int32(parsed), nil
}

// HasPrefixes returns true if the string s has any of the given prefixes.
func HasPrefixes(src string, prefixes ...string) bool {
	for _, prefix := range prefixes {
		if strings.HasPrefix(src, prefix) {
			return true
		}
	}
	return false
}

// ValidateEmail validates the email.
func ValidateEmail(email string) bool {
	if _, err := mail.ParseAddress(email); err != nil {
		return false
	}
	return true
}

func GenUUID() string {
	return uuid.New().String()
}

var letters = []rune("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")

// RandomString returns a random string with length n.
func RandomString(n int) (string, error) {
	var sb strings.Builder
	sb.Grow(n)
	for i := 0; i < n; i++ {
		// The reason for using crypto/rand instead of math/rand is that
		// the former relies on hardware to generate random numbers and
		// thus has a stronger source of random numbers.
		randNum, err := rand.Int(rand.Reader, big.NewInt(int64(len(letters))))
		if err != nil {
			return "", err
		}
		if _, err := sb.WriteRune(letters[randNum.Uint64()]); err != nil {
			return "", err
		}
	}
	return sb.String(), nil
}

// ReplaceString replaces all occurrences of old in slice with new.
func ReplaceString(slice []string, old, new string) []string {
	for i, s := range slice {
		if s == old {
			slice[i] = new
		}
	}
	return slice
}

// SanitizeUTF8 removes invalid UTF-8 sequences from a string.
// This is critical for gRPC which requires valid UTF-8 in all string fields.
// Invalid sequences are replaced with the Unicode replacement character (�).
func SanitizeUTF8(s string) string {
	if utf8.ValidString(s) {
		return s
	}

	// String contains invalid UTF-8, need to clean it
	var sb strings.Builder
	sb.Grow(len(s))

	for len(s) > 0 {
		r, size := utf8.DecodeRuneInString(s)
		if r == utf8.RuneError && size == 1 {
			// Invalid UTF-8 sequence, replace with replacement character
			sb.WriteRune(utf8.RuneError)
		} else {
			sb.WriteRune(r)
		}
		s = s[size:]
	}

	return sb.String()
}

// IsValidUTF8 checks if a string contains only valid UTF-8.
func IsValidUTF8(s string) bool {
	return utf8.ValidString(s)
}
