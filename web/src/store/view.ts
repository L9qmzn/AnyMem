/**
 * View Store
 *
 * Manages UI display preferences and layout settings.
 * This is a client state store that persists to localStorage.
 */
import { makeObservable, observable } from "mobx";
import { StandardState } from "./base-store";

const LOCAL_STORAGE_KEY = "memos-view-setting";

/**
 * Layout mode options
 */
export type LayoutMode = "LIST" | "MASONRY";

/**
 * View store state
 * Contains UI preferences for displaying memos
 */
class ViewState extends StandardState {
  /**
   * Sort order: true = ascending (oldest first), false = descending (newest first)
   */
  orderByTimeAsc: boolean = false;

  /**
   * Display layout mode
   * - LIST: Traditional vertical list
   * - MASONRY: Pinterest-style grid layout
   */
  layout: LayoutMode = "LIST";

  /**
   * Whether to keep inline #tags inside memo content
   * When disabled, memo snippets (without tags) are shown instead
   */
  preserveInlineTags: boolean = true;

  /**
   * Whether to show AI-generated tags beneath the manual tags.
   */
  showAiTags: boolean = true;

  constructor() {
    super();
    makeObservable(this, {
      orderByTimeAsc: observable,
      layout: observable,
      preserveInlineTags: observable,
      showAiTags: observable,
    });
  }

  /**
   * Override setPartial to persist to localStorage
   */
  setPartial(partial: Partial<ViewState>): void {
    // Validate layout if provided
    if (partial.layout !== undefined && !["LIST", "MASONRY"].includes(partial.layout)) {
      console.warn(`Invalid layout "${partial.layout}", ignoring`);
      return;
    }
    if (partial.preserveInlineTags !== undefined && typeof partial.preserveInlineTags !== "boolean") {
      console.warn(`Invalid preserveInlineTags value "${partial.preserveInlineTags}", ignoring`);
      return;
    }
    if (partial.showAiTags !== undefined && typeof partial.showAiTags !== "boolean") {
      console.warn(`Invalid showAiTags value "${partial.showAiTags}", ignoring`);
      return;
    }

    Object.assign(this, partial);

    // Persist to localStorage
    try {
      localStorage.setItem(
        LOCAL_STORAGE_KEY,
        JSON.stringify({
          orderByTimeAsc: this.orderByTimeAsc,
          layout: this.layout,
          preserveInlineTags: this.preserveInlineTags,
          showAiTags: this.showAiTags,
        }),
      );
    } catch (error) {
      console.warn("Failed to persist view settings:", error);
    }
  }
}

/**
 * View store instance
 */
const viewStore = (() => {
  const state = new ViewState();

  // Load from localStorage on initialization
  try {
    const cached = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (cached) {
      const data = JSON.parse(cached);

      // Validate and restore orderByTimeAsc
      if (Object.hasOwn(data, "orderByTimeAsc")) {
        state.orderByTimeAsc = Boolean(data.orderByTimeAsc);
      }

      // Validate and restore layout
      if (Object.hasOwn(data, "layout") && ["LIST", "MASONRY"].includes(data.layout)) {
        state.layout = data.layout as LayoutMode;
      }

      if (Object.hasOwn(data, "preserveInlineTags")) {
        state.preserveInlineTags = Boolean(data.preserveInlineTags);
      }

      if (Object.hasOwn(data, "showAiTags")) {
        state.showAiTags = Boolean(data.showAiTags);
      }
    }
  } catch (error) {
    console.warn("Failed to load view settings from localStorage:", error);
  }

  /**
   * Toggle sort order between ascending and descending
   */
  const toggleSortOrder = (): void => {
    state.setPartial({ orderByTimeAsc: !state.orderByTimeAsc });
  };

  /**
   * Set the layout mode
   *
   * @param layout - The layout mode to set
   */
  const setLayout = (layout: LayoutMode): void => {
    state.setPartial({ layout });
  };

  /**
   * Reset to default settings
   */
  const resetToDefaults = (): void => {
    state.setPartial({
      orderByTimeAsc: false,
      layout: "LIST",
      preserveInlineTags: true,
      showAiTags: true,
    });
  };

  /**
   * Clear persisted settings
   */
  const clearStorage = (): void => {
    localStorage.removeItem(LOCAL_STORAGE_KEY);
  };

  return {
    state,
    toggleSortOrder,
    setLayout,
    resetToDefaults,
    clearStorage,
  };
})();

export default viewStore;
