@echo off
REM 清除开发数据库中的所有 AI 标签
REM 使用方法: 直接双击运行或在命令行执行 clear_ai_tags.bat

echo.
echo ========================================
echo 清除 AI 标签工具 (开发测试用)
echo ========================================
echo.

set DB_FILE=..\memos_dev.db

if not exist "%DB_FILE%" (
    echo 错误: 找不到数据库文件 %DB_FILE%
    echo 请确保在 dev_tests 目录下运行此脚本
    pause
    exit /b 1
)

echo 正在清除所有 AI 标签...
echo.

sqlite3 "%DB_FILE%" "UPDATE memo SET payload = json_remove(payload, '$.aiTags') WHERE json_extract(payload, '$.aiTags') IS NOT NULL;"

if %errorlevel% equ 0 (
    echo ✓ AI 标签已清除
    echo.
    echo 统计信息:
    sqlite3 "%DB_FILE%" "SELECT '总备忘录数: ' || COUNT(*) FROM memo; SELECT '清除 AI 标签后: ' || SUM(CASE WHEN json_extract(payload, '$.aiTags') IS NULL THEN 1 ELSE 0 END) FROM memo;"
) else (
    echo ✗ 清除失败
)

echo.
pause
