import en from "./en";
import hi from "./hi";
import ta from "./ta";
import kn from "./kn";
import te from "./te";
import mr from "./mr";

export type LangCode = "en" | "hi" | "ta" | "kn" | "te" | "mr";
export type TranslationKeys = keyof typeof en;

export const LANGUAGES: { code: LangCode; label: string; nativeLabel: string }[] = [
  { code: "en", label: "English", nativeLabel: "English" },
  { code: "hi", label: "Hindi", nativeLabel: "हिन्दी" },
  { code: "ta", label: "Tamil", nativeLabel: "தமிழ்" },
  { code: "kn", label: "Kannada", nativeLabel: "ಕನ್ನಡ" },
  { code: "te", label: "Telugu", nativeLabel: "తెలుగు" },
  { code: "mr", label: "Marathi", nativeLabel: "मराठी" },
];

const translations: Record<LangCode, Record<string, string>> = {
  en,
  hi,
  ta,
  kn,
  te,
  mr,
};

export default translations;
