module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        'gblue': { 50:'#E8F0FE', 100:'#D2E3FC', 200:'#AECBFA', 500:'#4285F4', 600:'#1A73E8', 700:'#1967D2', 800:'#185ABC' },
        'gdoc':  { surface:'#F8F9FA', border:'#DADCE0', divider:'#E8EAED', hover:'#F1F3F4' },
        'gtext': { primary:'#202124', secondary:'#5F6368', disabled:'#9AA0A6' },
        'gstatus': { success:'#1E8E3E', warning:'#F9AB00', error:'#D93025' },
      },
      fontFamily: {
        sans: ['"Google Sans"', 'Roboto', 'Arial', 'sans-serif'],
        mono: ['"Roboto Mono"', 'monospace'],
      },
      boxShadow: {
        glow:  '0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15)',
        hover: '0 1px 3px 0 rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15)',
        modal: '0 8px 10px 1px rgba(0,0,0,0.14), 0 3px 14px 2px rgba(0,0,0,0.12)',
      },
      borderRadius: { g: '8px' },
    },
  },
  plugins: [],
};
