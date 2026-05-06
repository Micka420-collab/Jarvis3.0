import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

/**
 * Avatar minimal placeholder: une sphère/icosaèdre qui pulse en rythme avec le TTS.
 * La géométrie inférieure ("mâchoire") s'ouvre selon le visème courant.
 * À remplacer par un GLTF de tête avec blendshapes visèmes (Phase 1.5).
 */

const VISEME_OPEN: Record<string, number> = {
  sil: 0.0,
  PP: 0.05,
  FF: 0.1,
  TH: 0.25,
  DD: 0.2,
  kk: 0.2,
  CH: 0.2,
  SS: 0.15,
  nn: 0.15,
  RR: 0.3,
  aa: 0.85,
  E: 0.6,
  ih: 0.4,
  oh: 0.7,
  ou: 0.55,
};

function Head({ speaking, viseme }: { speaking: boolean; viseme: string }) {
  const mesh = useRef<THREE.Mesh>(null);
  const wire = useRef<THREE.Mesh>(null);
  const jaw = useRef<THREE.Mesh>(null);

  useFrame((_, dt) => {
    if (mesh.current) {
      const target = speaking ? 1.05 + Math.sin(performance.now() * 0.02) * 0.06 : 1.0;
      mesh.current.scale.lerp(new THREE.Vector3(target, target, target), 0.1);
      mesh.current.rotation.y += dt * 0.3;
    }
    if (wire.current) {
      wire.current.rotation.y -= dt * 0.4;
      wire.current.rotation.x += dt * 0.1;
    }
    if (jaw.current) {
      const open = VISEME_OPEN[viseme] ?? 0;
      const targetY = -0.4 - open * 0.4;
      jaw.current.position.lerp(new THREE.Vector3(0, targetY, 0.6), 0.4);
      const sx = 0.5 + open * 0.25;
      jaw.current.scale.lerp(new THREE.Vector3(sx, 0.15 + open * 0.2, 0.3), 0.4);
    }
  });

  return (
    <group>
      <mesh ref={mesh}>
        <icosahedronGeometry args={[1.2, 2]} />
        <meshStandardMaterial
          color={speaking ? "#4cc9f0" : "#4361ee"}
          emissive={speaking ? "#0f4c75" : "#1a237e"}
          metalness={0.6}
          roughness={0.2}
        />
      </mesh>
      <mesh ref={wire}>
        <icosahedronGeometry args={[1.7, 1]} />
        <meshBasicMaterial color="#4cc9f0" wireframe transparent opacity={0.25} />
      </mesh>
      <mesh ref={jaw} position={[0, -0.4, 0.6]} scale={[0.5, 0.15, 0.3]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color="#0f4c75" emissive="#1a237e" />
      </mesh>
    </group>
  );
}

export function Avatar3D({ speaking, viseme = "sil" }: { speaking: boolean; viseme?: string }) {
  return (
    <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={1.4} color="#4cc9f0" />
      <pointLight position={[-3, -3, 5]} intensity={0.8} color="#f72585" />
      <Head speaking={speaking} viseme={viseme} />
    </Canvas>
  );
}
