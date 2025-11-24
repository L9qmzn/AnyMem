import { observer } from "mobx-react-lite";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { aiServiceClient, RebuildTaskStatus } from "@/helpers/ai-service";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { userStore } from "@/store";
import { UserSetting_GeneralSetting } from "@/types/proto/api/v1/user_service";
import { useTranslate } from "@/utils/i18n";
import SettingGroup from "./SettingGroup";
import SettingRow from "./SettingRow";
import SettingSection from "./SettingSection";

const AiSection = observer(() => {
  const t = useTranslate();
  const generalSetting = userStore.state.userGeneralSetting;
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStatus, setRebuildStatus] = useState<RebuildTaskStatus | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const handleAutoGenerateTagsChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ autoGenerateTags: checked }, ["autoGenerateTags"]);
  };

  const handleAutoGenerateIndexChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ autoGenerateIndex: checked }, ["autoGenerateIndex"]);
  };

  const handleEnableAiSearchChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ enableAiSearch: checked }, ["enableAiSearch"]);
  };

  const pollRebuildStatus = async (creator: string) => {
    try {
      const status = await aiServiceClient.getRebuildStatus(creator);
      if (status) {
        setRebuildStatus(status);
        if (status.status === "completed") {
          setIsRebuilding(false);
          toast.success(t("setting.ai-section.rebuild-completed", { completed: status.completed, total: status.total }));
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        } else if (status.status === "failed") {
          setIsRebuilding(false);
          toast.error(t("setting.ai-section.rebuild-failed"));
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      }
    } catch (error) {
      console.error("Failed to poll rebuild status:", error);
    }
  };

  const handleRebuildIndex = async () => {
    const currentUser = userStore.state.currentUser;
    if (!currentUser) {
      toast.error("User not logged in");
      return;
    }

    setIsRebuilding(true);
    setRebuildStatus(null);

    try {
      await aiServiceClient.rebuildIndex(currentUser);
      toast.success(t("setting.ai-section.rebuild-started"));

      // Start polling for status
      pollingRef.current = setInterval(() => pollRebuildStatus(currentUser), 2000);
    } catch (error) {
      console.error("Failed to start rebuild:", error);
      toast.error(t("setting.ai-section.rebuild-failed"));
      setIsRebuilding(false);
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Provide default values if setting is not loaded yet
  const setting: UserSetting_GeneralSetting = generalSetting || {
    locale: "en",
    memoVisibility: "PRIVATE",
    theme: "system",
    autoGenerateTags: false,
    autoGenerateIndex: false,
    enableAiSearch: false,
  };

  return (
    <SettingSection>
      <SettingGroup title={t("setting.ai-section.title")}>
        <SettingRow label={t("setting.ai-section.auto-generate-tags")} description={t("setting.ai-section.auto-generate-tags-description")}>
          <Switch checked={setting.autoGenerateTags || false} onCheckedChange={handleAutoGenerateTagsChange} />
        </SettingRow>
        <SettingRow label={t("setting.ai-section.auto-generate-index")} description={t("setting.ai-section.auto-generate-index-description")}>
          <Switch checked={setting.autoGenerateIndex || false} onCheckedChange={handleAutoGenerateIndexChange} />
        </SettingRow>
        <SettingRow label={t("setting.ai-section.enable-ai-search")} description={t("setting.ai-section.enable-ai-search-description")}>
          <Switch checked={setting.enableAiSearch || false} onCheckedChange={handleEnableAiSearchChange} />
        </SettingRow>
        <SettingRow
          label={t("setting.ai-section.rebuild-index")}
          description={
            isRebuilding && rebuildStatus
              ? `${t("setting.ai-section.rebuilding-progress", { completed: rebuildStatus.completed, total: rebuildStatus.total })}`
              : t("setting.ai-section.rebuild-index-description")
          }
        >
          <Button onClick={handleRebuildIndex} disabled={isRebuilding} variant={isRebuilding ? "secondary" : "default"} size="sm">
            {isRebuilding ? t("setting.ai-section.rebuilding") : t("setting.ai-section.rebuild-index-button")}
          </Button>
        </SettingRow>
      </SettingGroup>
    </SettingSection>
  );
});

export default AiSection;
