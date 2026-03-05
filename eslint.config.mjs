import js from "@eslint/js";

export default [
  {
    ignores: [
      "app/web/static/js/htmx.min.js",
      "app/web/static/js/tailwind-config.js",
      "node_modules/**",
    ],
  },
  {
    ...js.configs.recommended,
    files: ["app/web/static/js/*.js"],
    languageOptions: {
      ecmaVersion: 2019,
      globals: {
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        location: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        fetch: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        Event: "readonly",
        CustomEvent: "readonly",
        DataTransfer: "readonly",
        File: "readonly",
        FileReader: "readonly",
        FormData: "readonly",
        MutationObserver: "readonly",
        ResizeObserver: "readonly",
        IntersectionObserver: "readonly",
        alert: "readonly",
        confirm: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        console: "readonly",
        Promise: "readonly",
      },
    },
    rules: {
      "no-unused-vars": [
        "error",
        {
          varsIgnorePattern: "^_",
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "no-empty": ["error", { "allowEmptyCatch": false }],
    },
  },
];
