import { observer } from "mobx-react-lite";
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

  const handleAutoGenerateTagsChange = async (checked: boolean) => {
    await userStore.updateUserGeneralSetting({ autoGenerateTags: checked }, ["autoGenerateTags"]);
  };

  // Provide default values if setting is not loaded yet
  const setting: UserSetting_GeneralSetting = generalSetting || {
    locale: "en",
    memoVisibility: "PRIVATE",
    theme: "system",
    autoGenerateTags: false,
  };

  return (
    <SettingSection>
      <SettingGroup title={t("setting.ai-section.title")}>
        <SettingRow label={t("setting.ai-section.auto-generate-tags")} description={t("setting.ai-section.auto-generate-tags-description")}>
          <Switch checked={setting.autoGenerateTags || false} onCheckedChange={handleAutoGenerateTagsChange} />
        </SettingRow>
      </SettingGroup>
    </SettingSection>
  );
});

export default AiSection;
