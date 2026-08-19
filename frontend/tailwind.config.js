/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{js,ts,jsx,tsx,mdx}",
    "./middleware/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  corePlugins: {
    // Keep Tailwind's base reset OFF: app/globals.css already owns base styles
    // and hand-styles the dashboard shell, slots, toggles, dialogs, and banners
    // with its own token system. Disabling preflight lights up the utility
    // classes (auth forms, nav, the subscribe flow) without resetting anything
    // globals.css already styles.
    preflight: false,
  },
  theme: {
    extend: {},
  },
  plugins: [],
};
