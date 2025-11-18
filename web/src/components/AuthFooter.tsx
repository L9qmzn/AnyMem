import { observer } from "mobx-react-lite";
import { cn } from "@/lib/utils";
import { instanceStore } from "@/store";
import LocaleSelect from "./LocaleSelect";
import ThemeSelect from "./ThemeSelect";

interface Props {
  className?: string;
}

const AuthFooter = observer(({ className }: Props) => {
  const handleLocaleChange = (locale: string) => {
    instanceStore.state.setPartial({ locale });
  };

  const handleThemeChange = (theme: string) => {
    instanceStore.state.setPartial({ theme });
  };

  return (
    <div className={cn("mt-4 flex flex-row items-center justify-center w-full gap-2", className)}>
      <LocaleSelect value={instanceStore.state.locale} onChange={handleLocaleChange} />
      <ThemeSelect value={instanceStore.state.theme} onValueChange={handleThemeChange} />
    </div>
  );
});

export default AuthFooter;
