import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import translations, { type LangCode, type TranslationKeys } from "./index";

interface LanguageContextValue {
  lang: LangCode;
  setLang: (code: LangCode) => void;
  t: (key: TranslationKeys | string) => string;
}

const STORAGE_KEY = "surakshashift_lang";

function getSavedLang(): LangCode | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && v in translations) return v as LangCode;
  } catch { /* SSR / privacy mode */ }
  return null;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(() => getSavedLang() || "en");

  const setLang = useCallback((code: LangCode) => {
    setLangState(code);
    try { localStorage.setItem(STORAGE_KEY, code); } catch { /* noop */ }
  }, []);

  const t = useCallback(
    (key: string): string => {
      const dict = translations[lang] || translations.en;
      return dict[key] ?? translations.en[key] ?? key;
    },
    [lang],
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useTranslation must be inside <LanguageProvider>");
  return ctx;
}

export function hasChosenLanguage(): boolean {
  return getSavedLang() !== null;
}
