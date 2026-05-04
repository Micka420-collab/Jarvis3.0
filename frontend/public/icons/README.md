# Icônes PWA

Génère les PNG depuis `frontend/public/favicon.svg` :

```bash
cd frontend/public/icons
# avec rsvg-convert (libsvg2)
rsvg-convert -w 192 -h 192 ../favicon.svg -o icon-192.png
rsvg-convert -w 512 -h 512 ../favicon.svg -o icon-512.png
rsvg-convert -w 512 -h 512 ../favicon.svg -o icon-512-maskable.png

# ou avec ImageMagick
magick -density 1024 -background none ../favicon.svg -resize 192x192 icon-192.png
magick -density 1024 -background none ../favicon.svg -resize 512x512 icon-512.png
cp icon-512.png icon-512-maskable.png

# ou en ligne : https://realfavicongenerator.net/  (uploader favicon.svg)
```

L'icône maskable doit avoir une "safe zone" centrée à 80 % du canvas (Android adaptive icons).
