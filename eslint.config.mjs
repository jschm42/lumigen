import js from "@eslint/js";

export default [
  {
    ignores: ["app/web/static/js/htmx.min.js", "node_modules/**"],
  },
  {
    ...js.configs.recommended,
    files: ["app/web/static/js/*.js"],
  },
];
