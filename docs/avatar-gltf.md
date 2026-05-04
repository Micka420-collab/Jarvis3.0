# Avatar GLTF haute-fidélité

Jarvis charge un avatar GLTF depuis `frontend/public/models/avatar.glb` (servi par nginx au runtime). S'il est absent, l'icosaèdre stylisé reprend la main automatiquement.

## Format requis

- **Format** : `.glb` (GLTF binaire)
- **Morph targets** : 52 blendshapes ARKit standard (au moins les `mouth*` et `jaw*`)
- **Échelle** : ~1,75 m de haut, origine au sol entre les pieds
- **Caméra** : avatar regarde l'axe Z+

## Sources recommandées

| Source | Avantages |
|---|---|
| [Ready Player Me](https://readyplayer.me/) | Export `.glb` direct, blendshapes ARKit prêts à l'emploi, gratuit |
| Mixamo + manual blendshapes | Avatar libre, mais blendshapes à ajouter dans Blender |
| Apple Memoji exporté via Reality Composer | Stylisé, ARKit natif |
| Custom Blender + plugin "Faceit" | Maximum de contrôle |

### Ready Player Me (le plus simple)

1. Va sur [readyplayer.me](https://readyplayer.me/) et crée un avatar
2. Récupère l'URL `.glb` (clique "Copy avatar URL")
3. Ajoute le paramètre de morph targets ARKit :
   ```
   https://models.readyplayer.me/<id>.glb?morphTargets=ARKit&textureAtlas=1024
   ```
4. Télécharge :
   ```bash
   curl -L "https://models.readyplayer.me/<id>.glb?morphTargets=ARKit&textureAtlas=1024" \
        -o frontend/public/models/avatar.glb
   ```
5. Recharge l'UI Jarvis — l'avatar prend la main.

## Mapping visèmes → blendshapes

Le mapping de chaque visème Oculus 15 vers les blendshapes ARKit est défini dans
[`frontend/src/lib/arkitBlendshapes.ts`](../frontend/src/lib/arkitBlendshapes.ts).

Exemple :
```ts
"aa": { jawOpen: 0.95, mouthShrugLower: 0.4 },
"ou": { jawOpen: 0.45, mouthPucker: 0.85, mouthFunnel: 0.3 },
```

Pour ajuster un visème, édite le mapping et rebuild le frontend (`make build` ou hot-reload Vite).

## Fonctionnalités automatiques

- **Lerp 30 ms** entre visèmes pour éviter les "à-coups"
- **Idle motion** : légère oscillation de tête (cou) en permanence
- **Clignement aléatoire** sur `eyeBlinkLeft/Right` toutes les 5 à 8 secondes
- **Speaking boost** : amplitude des mouvements augmente quand le TTS streame

## Performance

Sur un MacBook Pro M1 :
- 60 fps sur GLTF Ready Player Me 1024×1024 textures
- ~30 fps sur Raspberry Pi 5 — réduire les textures à 512 si lag

Sur le Raspberry Pi 4, désactiver l'avatar GLTF et utiliser le fallback icosaèdre.
