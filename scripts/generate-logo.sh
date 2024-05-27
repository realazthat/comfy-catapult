
npm install excalidraw-brute-export-cli

npx excalidraw-brute-export-cli -i .github/logo.excalidraw  \
  --scale 1 --dark-mode false --embed-scene false --background false --format svg  \
  --output .github/logo-stage1.svg

# Then:
# 1. open .github/logo-background.svg in inkscape.
# 2. load and center logo-stage1.svg.
# 3. export into logo-exported.svg.
