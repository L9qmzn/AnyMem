import { ChevronRightIcon, SparklesIcon } from "lucide-react";
import { observer } from "mobx-react-lite";
import useLocalStorage from "react-use/lib/useLocalStorage";
import { cn } from "@/lib/utils";
import memoFilterStore, { MemoFilter } from "@/store/memoFilter";
import { useTranslate } from "@/utils/i18n";

interface Props {
  readonly?: boolean;
  /**
   * AI tag count computed from filtered memos
   * Should be provided by parent component using useFilteredMemoStats
   */
  aiTagCount: Record<string, number>;
}

const AiTagsSection = observer((props: Props) => {
  const t = useTranslate();
  const [expanded, setExpanded] = useLocalStorage<boolean>("ai-tags-expanded", false);

  const tags = Object.entries(props.aiTagCount)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .sort((a, b) => b[1] - a[1]);

  const handleTagClick = (tag: string) => {
    const isActive = memoFilterStore.getFiltersByFactor("tagSearch").some((filter: MemoFilter) => filter.value === tag);
    if (isActive) {
      memoFilterStore.removeFilter((f: MemoFilter) => f.factor === "tagSearch" && f.value === tag);
    } else {
      memoFilterStore.addFilter({
        factor: "tagSearch",
        value: tag,
      });
    }
  };

  if (tags.length === 0) {
    return null;
  }

  return (
    <div className="w-full flex flex-col justify-start items-start mt-3 px-1 h-auto shrink-0 flex-nowrap hide-scrollbar">
      <div
        className="flex flex-row justify-start items-center w-full gap-1 mb-1 text-sm leading-6 text-muted-foreground select-none cursor-pointer hover:text-foreground transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronRightIcon className={cn("w-4 h-4 transition-transform", expanded && "rotate-90")} />
        <span>{t("common.ai-tags")}</span>
        <span className="text-xs opacity-60">({tags.length})</span>
      </div>
      {expanded && (
        <div className="w-full flex flex-row justify-start items-center relative flex-wrap gap-x-2 gap-y-1.5">
          {tags.map(([tag, amount]) => {
            const isActive = memoFilterStore.getFiltersByFactor("tagSearch").some((filter: MemoFilter) => filter.value === tag);
            return (
              <div
                key={tag}
                className={cn(
                  "shrink-0 w-auto max-w-full text-sm rounded-md leading-6 flex flex-row justify-start items-center select-none cursor-pointer transition-colors",
                  "hover:opacity-80",
                  isActive ? "text-primary" : "text-muted-foreground",
                )}
                onClick={() => handleTagClick(tag)}
              >
                <SparklesIcon className="w-3.5 h-auto shrink-0" />
                <div className="inline-flex flex-nowrap ml-0.5 gap-0.5 max-w-[calc(100%-16px)]">
                  <span className={cn("truncate", isActive ? "font-medium" : "")}>{tag}</span>
                  {amount > 1 && <span className="opacity-60 shrink-0">({amount})</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

export default AiTagsSection;
