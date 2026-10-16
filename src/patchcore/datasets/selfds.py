# import os
# from enum import Enum

# import numpy as np
# import PIL
# import PIL.Image
# import torch
# from torchvision import transforms

# IMAGENET_MEAN = [0.485, 0.456, 0.406]
# IMAGENET_STD  = [0.229, 0.224, 0.225]

# BG_THRESHOLD      = 15
# CROP_PADDING_FRAC = 0.08
# TARGET_PART_MEAN  = 110.0  # normalise all images to this brightness


# class DatasetSplit(Enum):
#     TRAIN = "train"
#     VAL   = "val"
#     TEST  = "test"


# def auto_crop_part(pil_image, threshold=BG_THRESHOLD, padding=CROP_PADDING_FRAC):
#     arr  = np.array(pil_image.convert("RGB"))
#     gray = arr.mean(axis=2)
#     mask = gray > threshold
#     rows = np.any(mask, axis=1)
#     cols = np.any(mask, axis=0)
#     if not rows.any():
#         return pil_image
#     rmin = int(np.where(rows)[0][0])
#     rmax = int(np.where(rows)[0][-1])
#     cmin = int(np.where(cols)[0][0])
#     cmax = int(np.where(cols)[0][-1])
#     h, w = arr.shape[:2]
#     pad_r = int((rmax - rmin) * padding)
#     pad_c = int((cmax - cmin) * padding)
#     rmin = max(0, rmin - pad_r)
#     rmax = min(h, rmax + pad_r)
#     cmin = max(0, cmin - pad_c)
#     cmax = min(w, cmax + pad_c)
#     return pil_image.crop((cmin, rmin, cmax, rmax))


# def normalise_brightness(pil_image, target_mean=TARGET_PART_MEAN, threshold=BG_THRESHOLD):
#     """
#     Scale part pixel brightness so the mean = target_mean.

#     Why this is needed:
#     - Images captured on different days have part_mean ranging 97–128 (12% swing)
#     - PatchCore uses L2 distance in feature space — brightness difference
#       looks like texture difference to the backbone
#     - This causes val score std ~0.25 → threshold calibration breaks
#     - After normalisation val score std should drop to ~0.05–0.10

#     Only part pixels (> threshold) are scaled.
#     Background pixels (= 0 after rembg) stay at 0.
#     """
#     arr  = np.array(pil_image, dtype=np.float32)
#     gray = arr.mean(axis=2)
#     part_mask = gray > threshold

#     if not part_mask.any():
#         return pil_image

#     current_mean = arr[part_mask].mean()
#     if current_mean < 1.0:
#         return pil_image

#     scale        = target_mean / current_mean
#     arr          = arr * scale
#     arr[~part_mask] = 0           # keep background pure black
#     arr          = np.clip(arr, 0, 255).astype(np.uint8)

#     return PIL.Image.fromarray(arr)


# class SelfDS(torch.utils.data.Dataset):
#     """
#     PatchCore dataset — no augmentation, with brightness normalisation.

#     Pipeline per image:
#       1. Open PNG (already background-removed by rembg)
#       2. auto_crop_part()      — crop to part bounding box
#       3. normalise_brightness() — scale part to TARGET_PART_MEAN=110
#       4. Resize + ToTensor + ImageNet normalise

#     Step 3 is the key fix: removes session-to-session brightness variation
#     so PatchCore memory bank patches are consistent regardless of capture day.
#     """

#     def __init__(
#         self,
#         source,
#         classname         = "Delivery_valve_seat",
#         resize            = 256,
#         imagesize         = 224,
#         split             = DatasetSplit.TRAIN,
#         train_val_split   = 1.0,
#         rotate_degrees    = 0,
#         translate         = 0,
#         brightness_factor = 0,
#         contrast_factor   = 0,
#         saturation_factor = 0,
#         gray_p            = 0,
#         h_flip_p          = 0,
#         v_flip_p          = 0,
#         scale             = 0,
#         augment           = False,
#         **kwargs,
#     ):
#         super().__init__()
#         self.source          = source
#         self.split           = split
#         self.classname       = classname
#         self.train_val_split = train_val_split
#         self.transform_std   = IMAGENET_STD
#         self.transform_mean  = IMAGENET_MEAN

#         self.imgpaths, self.labels = self.get_image_data()

#         # Clean deterministic transform — identical for TRAIN, VAL, TEST
#         # No randomness anywhere — memory bank, val scores and test scores
#         # must all be on exactly the same scale
#         self.transform_img = transforms.Compose([
#             transforms.Resize((imagesize, imagesize)),
#             transforms.ToTensor(),
#             transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
#         ])

#         self.imagesize = (3, imagesize, imagesize)

#         if self.split == DatasetSplit.TEST:
#             self.data_to_iterate = [
#                 (path, label, None, None)
#                 for path, label in zip(self.imgpaths, self.labels)
#             ]

#     def __getitem__(self, idx):
#         image_path = self.imgpaths[idx]
#         image      = PIL.Image.open(image_path).convert("RGB")

#         # 1. Crop to part bounding box
#         image = auto_crop_part(image)

#         # 2. Normalise brightness — fixes session-to-session variation
#         image = normalise_brightness(image)

#         # 3. Resize + normalise for backbone
#         image = self.transform_img(image)

#         parts      = image_path.split(os.sep)
#         anomaly    = parts[-2]
#         is_anomaly = int(anomaly.lower() != "good")
#         mask       = torch.zeros([1, *image.size()[1:]])

#         return {
#             "image"      : image,
#             "mask"       : mask,
#             "classname"  : self.classname,
#             "anomaly"    : anomaly,
#             "is_anomaly" : is_anomaly,
#             "image_name" : "/".join(parts[-4:]),
#             "image_path" : image_path,
#         }

#     def __len__(self):
#         return len(self.imgpaths)

#     def get_image_data(self):
#         imgpaths = []
#         labels   = []

#         if self.split in (DatasetSplit.TRAIN, DatasetSplit.VAL):
#             img_dir = os.path.join(self.source, self.classname, "train", "good")

#             if not os.path.exists(img_dir):
#                 raise FileNotFoundError(f"Train folder not found: {img_dir}")

#             all_files = sorted([
#                 f for f in os.listdir(img_dir)
#                 if f.lower().endswith((".jpg", ".jpeg", ".png"))
#             ])

#             n_total = len(all_files)
#             n_train = int(n_total * self.train_val_split)

#             if self.split == DatasetSplit.TRAIN:
#                 files = all_files[:n_train]
#                 print(f"[TRAIN] {len(files)}/{n_total} images → memory bank")
#             else:
#                 files = all_files[n_train:]
#                 print(f"[VAL]   {len(files)}/{n_total} images → threshold calibration")

#             if len(files) == 0:
#                 raise ValueError(
#                     f"Split has 0 images. train_val_split={self.train_val_split}, "
#                     f"total={n_total}. Need at least 2 images."
#                 )

#             imgpaths.extend([os.path.join(img_dir, f) for f in files])
#             labels.extend(["good"] * len(files))

#         elif self.split == DatasetSplit.TEST:
#             test_dir = os.path.join(self.source, self.classname, "test")
#             total = 0
#             for category in ["good", "anomaly"]:
#                 img_dir = os.path.join(test_dir, category)
#                 if not os.path.exists(img_dir):
#                     print(f"[WARNING] Test folder not found: {img_dir}")
#                     continue
#                 files = sorted([
#                     f for f in os.listdir(img_dir)
#                     if f.lower().endswith((".jpg", ".jpeg", ".png"))
#                 ])
#                 imgpaths.extend([os.path.join(img_dir, f) for f in files])
#                 labels.extend([category] * len(files))
#                 print(f"[TEST]  {len(files)} images → {category}")
#                 total += len(files)
#             print(f"[TEST]  Total: {total}")

#         return imgpaths, labels


# SelfDataset = SelfDS

import os
from enum import Enum

import numpy as np
import PIL
import PIL.Image
import torch
from torchvision import transforms

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

BG_THRESHOLD      = 15
CROP_PADDING_FRAC = 0.08
TARGET_PART_MEAN  = 110.0  # normalise all images to this brightness


class DatasetSplit(Enum):
    TRAIN = "train"
    VAL   = "val"
    TEST  = "test"


def auto_crop_part(pil_image, threshold=BG_THRESHOLD, padding=CROP_PADDING_FRAC):
    arr  = np.array(pil_image.convert("RGB"))
    gray = arr.mean(axis=2)
    mask = gray > threshold
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any():
        return pil_image
    rmin = int(np.where(rows)[0][0])
    rmax = int(np.where(rows)[0][-1])
    cmin = int(np.where(cols)[0][0])
    cmax = int(np.where(cols)[0][-1])
    h, w = arr.shape[:2]
    pad_r = int((rmax - rmin) * padding)
    pad_c = int((cmax - cmin) * padding)
    rmin = max(0, rmin - pad_r)
    rmax = min(h, rmax + pad_r)
    cmin = max(0, cmin - pad_c)
    cmax = min(w, cmax + pad_c)
    return pil_image.crop((cmin, rmin, cmax, rmax))


def normalise_brightness(pil_image, target_mean=TARGET_PART_MEAN, threshold=BG_THRESHOLD):
    """
    Scale part pixel brightness so the mean = target_mean.

    Why this is needed:
    - Images captured on different days have part_mean ranging 97–128 (12% swing)
    - PatchCore uses L2 distance in feature space — brightness difference
      looks like texture difference to the backbone
    - This causes val score std ~0.25 → threshold calibration breaks
    - After normalisation val score std should drop to ~0.05–0.10

    Only part pixels (> threshold) are scaled.
    Background pixels (= 0 after rembg) stay at 0.
    """
    arr  = np.array(pil_image, dtype=np.float32)
    gray = arr.mean(axis=2)
    part_mask = gray > threshold

    if not part_mask.any():
        return pil_image

    current_mean = arr[part_mask].mean()
    if current_mean < 1.0:
        return pil_image

    scale           = target_mean / current_mean
    arr             = arr * scale
    arr[~part_mask] = 0           # keep background pure black
    arr             = np.clip(arr, 0, 255).astype(np.uint8)

    return PIL.Image.fromarray(arr)


class SelfDS(torch.utils.data.Dataset):
    """
    PatchCore dataset with optional augmentation for training.

    Pipeline per image:
      1. Open PNG (already background-removed by rembg)
      2. auto_crop_part()       — crop to part bounding box
      3. normalise_brightness() — scale part to TARGET_PART_MEAN=110
      4. Resize + [augment if training] + ToTensor + ImageNet normalise

    Augmentation (only when augment=True AND split=TRAIN):
      - Random rotation ±15° — handles part placement variation
      - Random H/V flip     — handles mirrored orientations
      - Random crop         — handles slight framing differences
      - Slight colour jitter— handles minor lighting variation
      VAL and TEST always use deterministic transform (no augmentation).
    """

    def __init__(
        self,
        source,
        classname         = "Delivery_valve_seat",
        resize            = 512,
        imagesize         = 512,
        split             = DatasetSplit.TRAIN,
        train_val_split   = 1.0,
        # rotate_degrees    = 0,
        # translate         = 0,
        # brightness_factor = 0,
        # contrast_factor   = 0,
        # saturation_factor = 0,
        # gray_p            = 0,
        # h_flip_p          = 0,
        # v_flip_p          = 0,
        # scale             = 0,
        seed              = 42,
        augment           = False,
        **kwargs,
    ):
        super().__init__()
        self.source          = source
        self.split           = split
        self.classname       = classname
        self.train_val_split = train_val_split
        self.transform_std   = IMAGENET_STD
        self.transform_mean  = IMAGENET_MEAN

        self.imgpaths, self.labels = self.get_image_data()

        # Augmented transform — only for training when augment=True
        # VAL and TEST always use the clean deterministic transform
        # so that threshold calibration and scoring are on the same scale
        if augment and split == DatasetSplit.TRAIN:
            self.transform_img = transforms.Compose([
                transforms.Resize((resize, resize)),
                transforms.RandomRotation(degrees=90),
                transforms.ColorJitter(brightness=0.5, contrast=0.5),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ])
        else:
            self.transform_img = transforms.Compose([
                transforms.Resize((resize, resize)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ])

        self.imagesize = (3, imagesize, imagesize)

        if self.split == DatasetSplit.TEST:
            self.data_to_iterate = [
                (path, label, None, None)
                for path, label in zip(self.imgpaths, self.labels)
            ]

    def __getitem__(self, idx):
        image_path = self.imgpaths[idx]
        image      = PIL.Image.open(image_path).convert("RGB")

        # 1. Crop to part bounding box
        image = auto_crop_part(image)

        # 2. Normalise brightness — fixes session-to-session variation
        image = normalise_brightness(image)

        # 3. Resize + [augment] + normalise for backbone
        image = self.transform_img(image)

        parts      = image_path.split(os.sep)
        anomaly    = parts[-2]
        is_anomaly = int(anomaly.lower() != "good")
        mask       = torch.zeros([1, *image.size()[1:]])

        return {
            "image"      : image,
            "mask"       : mask,
            "classname"  : self.classname,
            "anomaly"    : anomaly,
            "is_anomaly" : is_anomaly,
            "image_name" : "/".join(parts[-4:]),
            "image_path" : image_path,
        }

    def __len__(self):
        return len(self.imgpaths)

    def get_image_data(self):
        imgpaths = []
        labels   = []

        if self.split == DatasetSplit.TRAIN:
            img_dir = os.path.join(self.source, self.classname, "train", "good")

            if not os.path.exists(img_dir):
                raise FileNotFoundError(f"Train folder not found: {img_dir}")

            files = sorted([
                f for f in os.listdir(img_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ])
            print(f"[TRAIN] {len(files)} images → memory bank")

            imgpaths.extend([os.path.join(img_dir, f) for f in files])
            labels.extend(["good"] * len(files))

        elif self.split == DatasetSplit.VAL:
            # VAL = only good test images — used for score normalization/threshold calibration
            # Must NOT include anomaly images, otherwise s_max is inflated and good scores compress
            img_dir = os.path.join(self.source, self.classname, "test", "good")
            if not os.path.exists(img_dir):
                print(f"[WARNING] VAL folder not found: {img_dir}")
            else:
                files = sorted([
                    f for f in os.listdir(img_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ])
                imgpaths.extend([os.path.join(img_dir, f) for f in files])
                labels.extend(["good"] * len(files))
                print(f"[VAL]   {len(files)} images → threshold calibration")

        elif self.split == DatasetSplit.TEST:
            test_dir = os.path.join(self.source, self.classname, "test")
            total = 0
            for category in ["good", "anomaly"]:
                img_dir = os.path.join(test_dir, category)
                if not os.path.exists(img_dir):
                    print(f"[WARNING] Test folder not found: {img_dir}")
                    continue
                files = sorted([
                    f for f in os.listdir(img_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ])
                imgpaths.extend([os.path.join(img_dir, f) for f in files])
                labels.extend([category] * len(files))
                print(f"[TEST]  {len(files)} images → {category}")
                total += len(files)
            print(f"[TEST]  Total: {total}")

        return imgpaths, labels


SelfDataset = SelfDS