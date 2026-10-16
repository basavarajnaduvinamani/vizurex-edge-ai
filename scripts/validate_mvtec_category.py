"""Validate the structure and basic integrity of one MVTec AD category."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image


def image_files(path: Path) -> list[Path]:
    return sorted(path.rglob("*.png"))


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--category", default="bottle")
    args = parser.parse_args()

    category = args.dataset_root / args.category
    train = image_files(category / "train" / "good")
    test_good = image_files(category / "test" / "good")
    test_anomaly = [
        path
        for defect_dir in (category / "test").iterdir()
        if defect_dir.is_dir() and defect_dir.name != "good"
        for path in image_files(defect_dir)
    ]
    masks = image_files(category / "ground_truth")

    unreadable: list[str] = []
    for path in train + test_good + test_anomaly + masks:
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:  # pragma: no cover - diagnostic path
            unreadable.append(f"{path}: {exc}")

    train_hashes = {digest(path) for path in train}
    overlap = [
        str(path.relative_to(category))
        for path in test_good + test_anomaly
        if digest(path) in train_hashes
    ]

    print(f"category={args.category}")
    print(f"train_good={len(train)}")
    print(f"test_good={len(test_good)}")
    print(f"test_anomaly={len(test_anomaly)}")
    print(f"ground_truth_masks={len(masks)}")
    print(f"unreadable={len(unreadable)}")
    print(f"exact_train_test_overlap={len(overlap)}")

    if unreadable or overlap:
        for item in unreadable + overlap:
            print(item)
        return 1
    if len(masks) != len(test_anomaly):
        print("mask count does not match anomalous test-image count")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
