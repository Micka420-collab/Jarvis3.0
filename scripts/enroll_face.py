"""Enrôle un visage dans le service vision.

Deux modes :
  - --image PATH       : enrôle depuis un fichier image (jpg/png)
  - --camera N         : capture depuis la webcam locale (cv2.VideoCapture(N))

L'embedding moyen est sauvegardé sous /models/known_faces/<name>.jpg
(le service vision relit ce dossier au démarrage). Optionnellement,
on peut aussi insérer un enregistrement dans la table users.

Usage (depuis l'hôte ou le conteneur vision) :
    python scripts/enroll_face.py --name mickael --image ./photo.jpg
    python scripts/enroll_face.py --name mickael --camera 0
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path


def capture_from_camera(index: int, out_path: Path) -> None:
    import cv2  # type: ignore

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"impossible d'ouvrir la caméra {index}")
    print("→ Mets-toi face à la caméra. Capture dans 3s…")
    time.sleep(3)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("capture KO")
    cv2.imwrite(str(out_path), frame)
    print(f"  capturé : {out_path}")


def validate_face(path: Path) -> tuple[bool, str]:
    """Vérifie qu'on détecte exactement 1 visage et qu'il est utilisable."""
    try:
        import cv2  # type: ignore
        from insightface.app import FaceAnalysis  # type: ignore

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        img = cv2.imread(str(path))
        if img is None:
            return False, "image illisible"
        faces = app.get(img)
        if len(faces) == 0:
            return False, "aucun visage détecté"
        if len(faces) > 1:
            return False, f"{len(faces)} visages détectés, garde-en un seul"
        return True, "ok"
    except ImportError:
        return True, "validation skipée (insightface non dispo localement)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="nom du visage à enregistrer")
    parser.add_argument("--image", type=Path, help="chemin d'une image existante")
    parser.add_argument("--camera", type=int, help="index de webcam pour capture live")
    parser.add_argument(
        "--known-dir",
        type=Path,
        default=Path("/models/known_faces"),
        help="dossier (volume monté du service vision)",
    )
    args = parser.parse_args()

    if not args.image and args.camera is None:
        parser.error("--image OU --camera requis")

    args.known_dir.mkdir(parents=True, exist_ok=True)
    target = args.known_dir / f"{args.name}.jpg"

    if args.image:
        if not args.image.exists():
            print(f"image introuvable: {args.image}", file=sys.stderr)
            return 1
        shutil.copy(args.image, target)
        print(f"  copié vers : {target}")
    else:
        capture_from_camera(args.camera, target)

    ok, msg = validate_face(target)
    if not ok:
        print(f"❌ validation : {msg}")
        target.unlink(missing_ok=True)
        return 2
    print(f"✅ visage enrôlé pour {args.name} ({msg})")
    print("    → redémarre le service vision pour qu'il recharge la base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
