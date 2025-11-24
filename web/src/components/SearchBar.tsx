import { SearchIcon, SparklesIcon } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { aiServiceClient } from "@/helpers/ai-service";
import { cn } from "@/lib/utils";
import { memoFilterStore, memoStore, userStore } from "@/store";
import { useTranslate } from "@/utils/i18n";
import MemoDisplaySettingMenu from "./MemoDisplaySettingMenu";

const SearchBar = observer(() => {
  const t = useTranslate();
  const [queryText, setQueryText] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isAiSearchEnabled = userStore.state.userGeneralSetting?.enableAiSearch || false;

  useEffect(() => {
    const handleGlobalShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleGlobalShortcut);
    return () => window.removeEventListener("keydown", handleGlobalShortcut);
  }, []);

  const onTextChange = (event: React.FormEvent<HTMLInputElement>) => {
    setQueryText(event.currentTarget.value);
  };

  const onKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const trimmedText = queryText.trim();
      if (trimmedText !== "") {
        if (isAiSearchEnabled) {
          // AI 语义搜索
          await handleAiSearch(trimmedText);
        } else {
          // 传统关键词搜索
          const words = trimmedText.split(/\s+/);
          words.forEach((word) => {
            memoFilterStore.addFilter({
              factor: "contentSearch",
              value: word,
            });
          });
          setQueryText("");
        }
      }
    }
  };

  const handleAiSearch = async (query: string) => {
    setIsSearching(true);
    try {
      // 获取当前用户名用于过滤搜索结果（只搜索自己的 memo）
      const currentUser = userStore.state.currentUser;
      const searchResults = await aiServiceClient.search({
        query,
        top_k: 20,
        search_mode: "hybrid",
        min_score: 0.5,
        creator: currentUser, // 用户级搜索过滤，格式如 "users/1"
      });

      if (searchResults.results.length === 0) {
        toast.error("No results found");
        setIsSearching(false);
        return;
      }

      // 获取搜索结果对应的 memo names（过滤空值）
      const memoNames = searchResults.results
        .map((result) => result.memo_name)
        .filter((name) => name && name.length > 0);

      if (memoNames.length === 0) {
        toast.error("No valid memo names in search results");
        setIsSearching(false);
        return;
      }

      // 清除所有现有过滤器
      memoFilterStore.clearAllFilters();

      // 使用 aiSearchResults 过滤器，值为逗号分隔的 memo names
      memoFilterStore.addFilter({
        factor: "aiSearchResults",
        value: memoNames.join(","),
      });

      // 添加搜索提示（用于显示，不会影响过滤）
      memoFilterStore.addFilter({
        factor: "contentSearch",
        value: `🔍 ${query}`,
      });

      // 加载所有搜索结果的 memo 到 store 中
      let loadedCount = 0;
      for (const memoName of memoNames.slice(0, 10)) {
        // 只加载前10个
        try {
          await memoStore.getOrFetchMemoByName(memoName, { skipCache: true });
          loadedCount++;
        } catch (error) {
          console.error(`Failed to load memo ${memoName}:`, error);
        }
      }

      if (loadedCount === 0) {
        toast.error("Failed to load any search results");
      } else {
        toast.success(`Found ${searchResults.results.length} results, loaded ${loadedCount}`);
      }

      setQueryText("");
    } catch (error) {
      console.error("AI search failed:", error);
      toast.error("AI search failed, falling back to keyword search");

      // 回退到传统搜索
      const words = query.split(/\s+/);
      words.forEach((word) => {
        memoFilterStore.addFilter({
          factor: "contentSearch",
          value: word,
        });
      });
      setQueryText("");
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="relative w-full h-auto flex flex-row justify-start items-center">
      {isAiSearchEnabled ? (
        <SparklesIcon className="absolute left-2 w-4 h-auto opacity-60 text-purple-500" />
      ) : (
        <SearchIcon className="absolute left-2 w-4 h-auto opacity-40 text-sidebar-foreground" />
      )}
      <input
        className={cn(
          "w-full text-sidebar-foreground leading-6 bg-sidebar border text-sm rounded-lg p-1 pl-8 outline-0",
          isAiSearchEnabled ? "border-purple-500/30" : "border-border",
        )}
        placeholder={isAiSearchEnabled ? t("memo.ai-search-placeholder") : t("memo.search-placeholder")}
        value={queryText}
        onChange={onTextChange}
        onKeyDown={onKeyDown}
        disabled={isSearching}
        ref={inputRef}
      />
      {isSearching && <div className="absolute right-10 top-2 text-sm text-muted-foreground">Searching...</div>}
      <MemoDisplaySettingMenu className="absolute right-2 top-2 text-sidebar-foreground" />
    </div>
  );
});

export default SearchBar;
