import appletManifest from "./applet-manifest.generated.json";

const RAW_APPLETS = process.env.REACT_APP_APPLETS ?? "all";

export const ENABLED_APPLETS = RAW_APPLETS.split(",")
  .map(value => value.trim())
  .filter(Boolean);

export function isAppletEnabled(applet: string): boolean {
  return ENABLED_APPLETS.includes("all") || ENABLED_APPLETS.includes(applet);
}

export function areAnyAppletsEnabled(applets: string[]): boolean {
  return applets.some(isAppletEnabled);
}

// Meeting decision: Chat + RAG + Workspaces are base platform functionality.
const BASE_FRONTEND_APPS = new Set(["chat", "workspaces"]);

export function isBaseChatPlatformEnabled(): boolean {
  return true;
}

const APP_ID_TO_PAGES: Record<string, string[]> = {
  talent: ["talent-intelligence", "reference-checks"],
  chat: ["chat"],
  workspaces: ["workspaces"],
  sow: ["sow"],
  "content-research": ["content-research"],
  adoption: ["adoption"],
  "deal-intelligence": ["coming-soon"],
  "rfp-responder": ["coming-soon"],
  "customer-health": ["coming-soon"],
  "ma-analyst": ["coming-soon"],
  "spend-optimizer": ["coming-soon"],
  "regulatory-radar": ["coming-soon"],
  "onboarding-copilot": ["coming-soon"],
  "competitive-intel": ["coming-soon"],
  "campaign-optimizer": ["coming-soon"],
  "contract-hub": ["coming-soon"],
  "it-service-desk": ["coming-soon"],
  "supply-chain": ["coming-soon"],
  "product-insights": ["coming-soon"],
  "eliza-engage": ["coming-soon"],
  "incident-commander": ["coming-soon"],
  "partner-intelligence": ["coming-soon"],
  "board-report-generator": ["coming-soon"],
  "knowledge-miner": ["coming-soon"],
  "brand-guardian": ["coming-soon"],
};

const APPLET_TO_PAGES: Record<string, string[]> =
  appletManifest.applet_to_pages as Record<string, string[]>;

const ENABLED_PAGES = (() => {
  if (ENABLED_APPLETS.includes("all")) {
    return null;
  }

  const pages = new Set<string>();
  for (const applet of ENABLED_APPLETS) {
    const manifestPages = APPLET_TO_PAGES[applet];
    if (!manifestPages) {
      continue;
    }
    for (const page of manifestPages) {
      pages.add(page);
    }
  }
  return pages;
})();

export function isFrontendPageEnabled(pageKey: string): boolean {
  if (ENABLED_PAGES === null) {
    return true;
  }
  return ENABLED_PAGES.has(pageKey);
}

export function isFrontendAppEnabled(appId: string): boolean {
  if (BASE_FRONTEND_APPS.has(appId)) {
    return true;
  }

  const mappedPages = APP_ID_TO_PAGES[appId];
  if (!mappedPages) {
    // Unknown app ids default to hidden for modular builds.
    return false;
  }
  return mappedPages.some(isFrontendPageEnabled);
}
