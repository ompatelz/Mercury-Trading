import { motion } from "motion/react";

type SkiperThemeToggleProps = {
  isDark: boolean;
  onToggle: () => void;
};

/**
 * Adapted from Skiper UI's free `skiper4` theme-toggle component.
 * Attribution: https://skiper-ui.com/v1/skiper4
 */
export function SkiperThemeToggle({ isDark, onToggle }: SkiperThemeToggleProps) {
  return (
    <button
      type="button"
      className="themeToggle"
      onClick={onToggle}
      aria-label={isDark ? "Use light theme" : "Use dark theme"}
      aria-pressed={isDark}
    >
      <svg aria-hidden="true" fill="currentColor" strokeLinecap="round" viewBox="0 0 32 32">
        <clipPath id="mercury-skiper-theme-toggle">
          <motion.path
            initial={false}
            animate={{ y: isDark ? 10 : 0, x: isDark ? -12 : 0 }}
            transition={{ ease: "easeInOut", duration: 0.35 }}
            d="M0-5h30a1 1 0 0 0 9 13v24H0Z"
          />
        </clipPath>
        <g clipPath="url(#mercury-skiper-theme-toggle)">
          <motion.circle
            initial={false}
            animate={{ r: isDark ? 10 : 8 }}
            transition={{ ease: "easeInOut", duration: 0.35 }}
            cx="16"
            cy="16"
          />
          <motion.g
            initial={false}
            animate={{ rotate: isDark ? -100 : 0, scale: isDark ? 0.5 : 1, opacity: isDark ? 0 : 1 }}
            transition={{ ease: "easeInOut", duration: 0.35 }}
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M16 5.5v-4" />
            <path d="M16 30.5v-4" />
            <path d="M1.5 16h4" />
            <path d="M26.5 16h4" />
            <path d="m23.4 8.6 2.8-2.8" />
            <path d="m5.7 26.3 2.9-2.9" />
            <path d="m5.8 5.8 2.8 2.8" />
            <path d="m23.4 23.4 2.9 2.9" />
          </motion.g>
        </g>
      </svg>
    </button>
  );
}
