import { observer } from "mobx-react-lite";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { aiServiceClient, RebuildTaskStatus } from "@/helpers/ai-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import useCurrentUser from "@/hooks/useCurrentUser";
import { instanceStore, userStore } from "@/store";
import { instanceSettingNamePrefix } from "@/store/common";
import { InstanceSetting_AiSetting, InstanceSetting_Key } from "@/types/proto/api/v1/instance_service";
import { User_Role } from "@/types/proto/api/v1/user_service";
import { UserSetting_GeneralSetting } from "@/types/proto/api/v1/user_service";
import { useTranslate } from "@/utils/i18n";
import SettingGroup from "./SettingGroup";
import SettingRow from "./SettingRow";
import SettingSection from "./SettingSection";

const AiSection = observer(() => {
  const t = useTranslate();
  const generalSetting = userStore.state.userGeneralSetting;
  const currentUser = useCurrentUser();
  const isHost = currentUser?.role === User_Role.HOST;
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStatus, setRebuildStatus] = useState<RebuildTaskStatus | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Instance AI settings (only for host)
  const [aiServiceUrl, setAiServiceUrl] = useState("");
  const [originalAiServiceUrl, setOriginalAiServiceUrl] = useState("");

  useEffect(() => {
    if (isHost) {
      // Fetch AI setting if not already loaded
      instanceStore.fetchInstanceSetting(InstanceSetting_Key.AI).then(() => {
        const aiSetting = instanceStore.getInstanceSettingByKey(InstanceSetting_Key.AI)?.aiSetting;
        const url = aiSetting?.aiServiceUrl || "http://127.0.0.1:8000";
        setAiServiceUrl(url);
        setOriginalAiServiceUrl(url);
      });
    }
  }, [isHost]);

  const handleSaveAiServiceUrl = async () => {
    try {
      await instanceStore.upsertInstanceSetting({
        name: `${instanceSettingNamePrefix}${InstanceSetting_Key.AI}`,
        aiSetting: InstanceSetting_AiSetting.fromPartial({
          aiServiceUrl: aiServiceUrl,
        }),
      });
      setOriginalAiServiceUrl(aiServiceUrl);
      toast.success(t("common.updated"));
    } catch (error) {
      console.error("Failed to update AI service URL:", error);
      toast.error(t("common.update-failed"));
    }
  };

  const handleAutoGenerateTagsChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ autoGenerateTags: checked }, ["autoGenerateTags"]);
  };

  const handleAutoGenerateIndexChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ autoGenerateIndex: checked }, ["autoGenerateIndex"]);
  };

  const handleDeveloperModeChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ developerMode: checked }, ["developerMode"]);
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
    developerMode: false,
  };

  return (
    <SettingSection>
      <SettingGroup title={t("setting.ai-section.title")}>
        {isHost && (
          <SettingRow label={t("setting.ai-section.ai-service-url")} description={t("setting.ai-section.ai-service-url-description")}>
            <div className="flex items-center gap-2">
              <Input
                className="w-64"
                value={aiServiceUrl}
                onChange={(e) => setAiServiceUrl(e.target.value)}
                placeholder="http://127.0.0.1:8000"
              />
              <Button onClick={handleSaveAiServiceUrl} disabled={aiServiceUrl === originalAiServiceUrl} size="sm">
                {t("common.save")}
              </Button>
            </div>
          </SettingRow>
        )}
        <SettingRow label={t("setting.ai-section.auto-generate-tags")} description={t("setting.ai-section.auto-generate-tags-description")}>
          <Switch checked={setting.autoGenerateTags || false} onCheckedChange={handleAutoGenerateTagsChange} />
        </SettingRow>
        <SettingRow label={t("setting.ai-section.auto-generate-index")} description={t("setting.ai-section.auto-generate-index-description")}>
          <Switch checked={setting.autoGenerateIndex || false} onCheckedChange={handleAutoGenerateIndexChange} />
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
        <SettingRow label={t("setting.ai-section.developer-mode")} description={t("setting.ai-section.developer-mode-description")}>
          <Switch checked={setting.developerMode || false} onCheckedChange={handleDeveloperModeChange} />
        </SettingRow>
      </SettingGroup>
    </SettingSection>
  );
});

export default AiSection;
