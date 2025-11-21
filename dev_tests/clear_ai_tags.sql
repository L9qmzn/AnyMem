-- 清除所有 memo 的 AI 标签 (开发测试用)
-- 使用方法: sqlite3 memos_dev.db < dev_tests/clear_ai_tags.sql

UPDATE memo
SET payload = json_remove(payload, '$.aiTags')
WHERE json_extract(payload, '$.aiTags') IS NOT NULL;

-- 显示更新结果
SELECT
    COUNT(*) as total_memos,
    SUM(CASE WHEN json_extract(payload, '$.aiTags') IS NULL THEN 1 ELSE 0 END) as memos_without_ai_tags,
    SUM(CASE WHEN json_extract(payload, '$.aiTags') IS NOT NULL THEN 1 ELSE 0 END) as memos_with_ai_tags
FROM memo;
