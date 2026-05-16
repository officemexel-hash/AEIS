import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // F-014 audit fix: pragmatic rule pragmatism — downgrade most prevalent
  // type-debt rules to warnings so lint distinguishes real bugs (errors)
  // from accumulated debt (warnings). Cleanup tracked as separate ticket.
  // Top counts before this override (npm run lint, 2026-04-26):
  //   744 @typescript-eslint/no-explicit-any   -> warn (debt; large refactor)
  //   203 @typescript-eslint/no-unused-vars    -> warn unless _-prefixed
  //   73  react-hooks/exhaustive-deps          -> warn (tracked hook-deps debt)
  // R2.3 audit: React Compiler migration rules are kept visible as warnings
  // until the affected legacy surfaces are refactored. Hard errors remain for
  // Rules of Hooks, set-state-in-render, immutability, syntax, and type parser
  // failures.
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "react/no-unescaped-entities": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/static-components": "warn",
    },
  },
]);

export default eslintConfig;
