/**
 * Avatar GLTF haute-fidélité avec blendshapes ARKit.
 * Charge /models/avatar.glb (Ready Player Me, Mixamo, ou exporté Blender avec
 * les 52 morph targets ARKit standard).
 *
 * Visème courant → mapping ARKit → morphTargetInfluences sur tous les meshes
 * skinnés du GLTF. Lerp fluide entre les transitions.
 *
 * Si /models/avatar.glb est absent ou 404, on retombe sur l'icosaèdre stylisé
 * (fallback pour démarrage zero-config).
 */

import { useGLTF } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { ARKitBlendshape, VISEME_TO_ARKIT, lerpWeights } from "../lib/arkitBlendshapes";
import { Avatar3D as AvatarFallback } from "./Avatar3D";

type Weights = Partial<Record<ARKitBlendshape, number>>;

const MODEL_URL = "/models/avatar.glb";

function AvatarMesh({ viseme, speaking }: { viseme: string; speaking: boolean }) {
  const gltf = useGLTF(MODEL_URL);
  const root = useRef<THREE.Group>(null);
  const targetWeights = useRef<Weights>({});
  const currentWeights = useRef<Weights>({});

  // Index morph targets disponibles (tous les meshes skinnés)
  const morphMap = useMemo(() => {
    const map: { mesh: THREE.Mesh; index: number; key: string }[] = [];
    gltf.scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if ((mesh.morphTargetDictionary as unknown) && mesh.morphTargetInfluences) {
        const dict = mesh.morphTargetDictionary as Record<string, number>;
        for (const [name, idx] of Object.entries(dict)) {
          map.push({ mesh, index: idx, key: name });
        }
      }
    });
    return map;
  }, [gltf]);

  useEffect(() => {
    targetWeights.current = VISEME_TO_ARKIT[viseme] ?? {};
  }, [viseme]);

  useFrame((_, dt) => {
    // lerp doux vers la cible (~30 ms de temps de réponse)
    const t = Math.min(1, dt * 18);
    currentWeights.current = lerpWeights(currentWeights.current, targetWeights.current, t);

    // Applique sur tous les morph targets pertinents
    for (const { mesh, index, key } of morphMap) {
      const w = (currentWeights.current as Record<string, number>)[key];
      if (mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[index] = w ?? 0;
      }
    }

    // Idle "vivant" : léger mouvement de tête + clignement aléatoire
    if (root.current) {
      const time = performance.now() * 0.001;
      root.current.rotation.y = Math.sin(time * 0.4) * 0.05 + (speaking ? Math.sin(time * 4) * 0.02 : 0);
      root.current.rotation.x = Math.sin(time * 0.3) * 0.02;
    }

    // Clignement périodique
    const blink = Math.max(0, Math.sin(performance.now() * 0.001 * Math.PI * 0.18));
    const blinkValue = blink > 0.985 ? 1 : 0;
    for (const { mesh, index, key } of morphMap) {
      if ((key === "eyeBlinkLeft" || key === "eyeBlinkRight") && mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[index] = blinkValue;
      }
    }
  });

  return (
    <group ref={root} position={[0, -1.5, 0]}>
      <primitive object={gltf.scene} />
    </group>
  );
}

/**
 * Composant principal exporté.
 * Si le fichier n'existe pas, useGLTF lèvera une erreur attrapée par
 * l'ErrorBoundary et on tombera sur l'icosaèdre.
 */
export function AvatarGLTF({ speaking, viseme = "sil" }: { speaking: boolean; viseme?: string }) {
  const [hasModel, setHasModel] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(MODEL_URL, { method: "HEAD" })
      .then((r) => setHasModel(r.ok))
      .catch(() => setHasModel(false));
  }, []);

  if (hasModel === false) {
    return <AvatarFallback speaking={speaking} viseme={viseme} />;
  }
  if (hasModel === null) {
    return null;
  }

  return (
    <Canvas camera={{ position: [0, 0.1, 1.6], fov: 30 }}>
      <ambientLight intensity={0.7} />
      <directionalLight position={[2, 3, 4]} intensity={1.4} color="#ffffff" />
      <pointLight position={[-2, 1, 2]} intensity={0.5} color="#4cc9f0" />
      <Suspense fallback={null}>
        <AvatarMesh viseme={viseme} speaking={speaking} />
      </Suspense>
    </Canvas>
  );
}

useGLTF.preload(MODEL_URL);
