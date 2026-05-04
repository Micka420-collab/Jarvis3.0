import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

/**
 * Avatar minimal placeholder: une sphère/icosaèdre qui pulse en rythme avec le TTS.
 * À remplacer par un GLTF de tête avec blendshapes visèmes (Phase 1.5).
 */
function Head({ speaking }: { speaking: boolean }) {
  const mesh = useRef<THREE.Mesh>(null);
  const wire = useRef<THREE.Mesh>(null);
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
    </group>
  );
}

export function Avatar3D({ speaking }: { speaking: boolean }) {
  return (
    <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={1.4} color="#4cc9f0" />
      <pointLight position={[-3, -3, 5]} intensity={0.8} color="#f72585" />
      <Head speaking={speaking} />
    </Canvas>
  );
}
