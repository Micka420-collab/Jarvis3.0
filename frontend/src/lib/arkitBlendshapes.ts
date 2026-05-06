/**
 * Mapping visèmes Oculus 15 → blendshapes ARKit (52 morph targets standard).
 * Référence ARKit:
 *   https://developer.apple.com/documentation/arkit/arfaceanchor/blendshapelocation
 *
 * Chaque visème active plusieurs blendshapes avec des poids relatifs,
 * pour un rendu plus naturel qu'un simple "jaw open".
 */

export type ARKitBlendshape =
  | "jawOpen"
  | "jawForward"
  | "mouthClose"
  | "mouthFunnel"
  | "mouthPucker"
  | "mouthLeft"
  | "mouthRight"
  | "mouthSmileLeft"
  | "mouthSmileRight"
  | "mouthFrownLeft"
  | "mouthFrownRight"
  | "mouthDimpleLeft"
  | "mouthDimpleRight"
  | "mouthStretchLeft"
  | "mouthStretchRight"
  | "mouthRollLower"
  | "mouthRollUpper"
  | "mouthShrugLower"
  | "mouthShrugUpper"
  | "mouthPressLeft"
  | "mouthPressRight"
  | "mouthLowerDownLeft"
  | "mouthLowerDownRight"
  | "mouthUpperUpLeft"
  | "mouthUpperUpRight"
  | "tongueOut"
  | "eyeBlinkLeft"
  | "eyeBlinkRight"
  | "eyeLookDownLeft"
  | "eyeLookDownRight"
  | "eyeLookInLeft"
  | "eyeLookInRight"
  | "eyeLookOutLeft"
  | "eyeLookOutRight"
  | "eyeLookUpLeft"
  | "eyeLookUpRight"
  | "eyeSquintLeft"
  | "eyeSquintRight"
  | "eyeWideLeft"
  | "eyeWideRight"
  | "browDownLeft"
  | "browDownRight"
  | "browInnerUp"
  | "browOuterUpLeft"
  | "browOuterUpRight"
  | "cheekPuff"
  | "cheekSquintLeft"
  | "cheekSquintRight"
  | "noseSneerLeft"
  | "noseSneerRight";

type Weights = Partial<Record<ARKitBlendshape, number>>;

/** Visème Oculus 15 → poids des blendshapes ARKit. */
export const VISEME_TO_ARKIT: Record<string, Weights> = {
  sil: {},
  PP: { mouthClose: 0.85, mouthRollUpper: 0.3, mouthRollLower: 0.3 },
  FF: { jawOpen: 0.1, mouthFunnel: 0.4, mouthLowerDownLeft: 0.3, mouthLowerDownRight: 0.3 },
  TH: { jawOpen: 0.2, tongueOut: 0.5, mouthShrugUpper: 0.2 },
  DD: { jawOpen: 0.25, mouthFunnel: 0.15, mouthRollUpper: 0.2 },
  kk: { jawOpen: 0.25, mouthShrugLower: 0.3 },
  CH: { jawOpen: 0.25, mouthFunnel: 0.6, mouthPucker: 0.4 },
  SS: { jawOpen: 0.15, mouthStretchLeft: 0.3, mouthStretchRight: 0.3 },
  nn: { jawOpen: 0.2, mouthClose: 0.2 },
  RR: { jawOpen: 0.35, mouthPucker: 0.5, mouthFunnel: 0.3 },
  aa: { jawOpen: 0.95, mouthShrugLower: 0.4 },
  E: { jawOpen: 0.55, mouthSmileLeft: 0.2, mouthSmileRight: 0.2, mouthStretchLeft: 0.25, mouthStretchRight: 0.25 },
  ih: { jawOpen: 0.35, mouthStretchLeft: 0.3, mouthStretchRight: 0.3 },
  oh: { jawOpen: 0.7, mouthFunnel: 0.5, mouthPucker: 0.4 },
  ou: { jawOpen: 0.45, mouthPucker: 0.85, mouthFunnel: 0.3 },
};

/** Lerp entre deux ensembles de poids — utile pour transitions fluides. */
export function lerpWeights(a: Weights, b: Weights, t: number): Weights {
  const out: Weights = {};
  const keys = new Set<ARKitBlendshape>([
    ...(Object.keys(a) as ARKitBlendshape[]),
    ...(Object.keys(b) as ARKitBlendshape[]),
  ]);
  for (const k of keys) {
    const va = a[k] ?? 0;
    const vb = b[k] ?? 0;
    out[k] = va + (vb - va) * t;
  }
  return out;
}
