import "@github/relative-time-element";
import { observer } from "mobx-react-lite";
import { createRoot } from "react-dom/client";
import { Toaster } from "react-hot-toast";
import { RouterProvider } from "react-router-dom";
import i18n from "./i18n";
import "./index.css";
import router from "./router";
// Configure MobX before importing any stores
import "./store/config";
import { instanceStore } from "./store";
import { initialInstanceStore } from "./store/instance";
import { initialUserStore } from "./store/user";
import { applyThemeEarly } from "./utils/theme";
import "leaflet/dist/leaflet.css";

// Apply theme early to prevent flash of wrong theme
applyThemeEarly();

const Main = observer(() => (
  <>
    <RouterProvider router={router} />
    <Toaster position="top-right" />
  </>
));

(async () => {
  await initialInstanceStore();
  await initialUserStore();

  // Set i18n language before rendering to prevent flash of wrong language
  const initialLocale = instanceStore.state.locale;
  await i18n.changeLanguage(initialLocale);
  document.documentElement.setAttribute("lang", initialLocale);

  const container = document.getElementById("root");
  const root = createRoot(container as HTMLElement);
  root.render(<Main />);
})();
