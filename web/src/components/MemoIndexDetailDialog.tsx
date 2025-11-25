import { FileTextIcon, ImageIcon, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { aiServiceClient, MemoIndexInfo } from "@/helpers/ai-service";
import { Memo } from "@/types/proto/api/v1/memo_service";
import { useTranslate } from "@/utils/i18n";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  memo: Memo;
}

function MemoIndexDetailDialog({ open, onOpenChange, memo }: Props) {
  const t = useTranslate();
  const [loading, setLoading] = useState(false);
  const [indexInfo, setIndexInfo] = useState<MemoIndexInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && memo) {
      fetchIndexInfo();
    }
  }, [open, memo]);

  const fetchIndexInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const info = await aiServiceClient.getMemoIndexInfo(memo.name, true);
      setIndexInfo(info);
    } catch (err) {
      setError(t("memo.index-detail.fetch-error"));
      console.error("Failed to fetch index info:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("memo.index-detail.title")}</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-destructive text-sm py-4">{error}</div>
        ) : !indexInfo ? (
          <div className="text-muted-foreground text-sm py-4">{t("memo.not-indexed")}</div>
        ) : !indexInfo.indexed ? (
          <div className="text-muted-foreground text-sm py-4">{t("memo.not-indexed")}</div>
        ) : (
          <div className="space-y-4">
            {/* Basic info */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">{t("memo.index-detail.memo-uid")}:</span>
                <span className="ml-2 font-mono text-xs">{indexInfo.memo_uid}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t("memo.index-detail.status")}:</span>
                <span className="ml-2 text-green-600">{t("memo.indexed")}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t("memo.index-detail.text-vectors")}:</span>
                <span className="ml-2">{indexInfo.text_vectors}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t("memo.index-detail.image-vectors")}:</span>
                <span className="ml-2">{indexInfo.image_vectors}</span>
              </div>
            </div>

            {/* Text chunks */}
            {indexInfo.detail?.text_chunks && indexInfo.detail.text_chunks.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  <FileTextIcon className="h-4 w-4" />
                  {t("memo.index-detail.text-chunks")} ({indexInfo.detail.text_chunks.length})
                </h4>
                <div className="space-y-2">
                  {indexInfo.detail.text_chunks.map((chunk, idx) => (
                    <div key={idx} className="bg-muted rounded-md p-3 text-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-muted-foreground font-mono">{chunk.doc_id}</span>
                        <span className="text-xs bg-secondary px-1.5 py-0.5 rounded">{chunk.content_type}</span>
                      </div>
                      <p className="text-foreground whitespace-pre-wrap break-words">{chunk.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Images */}
            {indexInfo.detail?.images && indexInfo.detail.images.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  <ImageIcon className="h-4 w-4" />
                  {t("memo.index-detail.images")} ({indexInfo.detail.images.length})
                </h4>
                <div className="space-y-2">
                  {indexInfo.detail.images.map((img, idx) => (
                    <div key={idx} className="bg-muted rounded-md p-3 text-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-muted-foreground font-mono">{img.doc_id}</span>
                        {img.filename && <span className="text-xs bg-secondary px-1.5 py-0.5 rounded">{img.filename}</span>}
                      </div>
                      <div className="mt-2">
                        <span className="text-xs text-muted-foreground">{t("memo.index-detail.caption")}:</span>
                        <p className="text-foreground mt-1">{img.caption || t("memo.index-detail.no-caption")}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No detail available */}
            {(!indexInfo.detail || (indexInfo.detail.text_chunks.length === 0 && indexInfo.detail.images.length === 0)) && (
              <div className="text-muted-foreground text-sm py-4 text-center">{t("memo.index-detail.no-detail")}</div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default MemoIndexDetailDialog;
