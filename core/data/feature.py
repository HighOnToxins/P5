import logging
import os.path
import numpy as np
import pandas as pd
from PIL import Image
from skimage.feature import local_binary_pattern, graycomatrix, SIFT
from core.util.constants import FEATURE_DIR_PATH, IMGDIR_PATH, DATASET_PATH, PATH_SEP
from core.util.logging.logable import Logable
from core.util.util import setup_log

FTS = ['sift', 'lbp', 'glcm']

class FeatureExtractor(Logable):
    def __init__(self,
                 img_dir_path=IMGDIR_PATH,
                 feature_dir_path=FEATURE_DIR_PATH,
                 log_level=logging.DEBUG):
        super().__init__()
        setup_log(log_level=log_level)
        self.save_path = feature_dir_path
        self.img_path = img_dir_path
        self._mk_ft_dirs()


    def pre_process(self, df: pd.DataFrame, feature="", should_bb=True, should_resize=False, **kwargs):
        ft = getattr(self, feature, None)
        paths = np.full(len(df.index), fill_value=np.nan).tolist()
        for index, row in df.iterrows():
            self.log.debug(row)
            p_new = self.path_from_row_ft(row, feature)
            l_new = self.l_dirpath_from_row(row, feature)
            if not os.path.exists(p_new):
                with Image.open(row['path']) as img:
                    if feature == "lbp":
                        lbp_arr = ft(img, kwargs.get('method', 'ror'), kwargs.get('radius', 1))
                        img = Image.fromarray(lbp_arr)
                        paths[int(index)] = p_new
                    elif feature == "sift":
                        pass
                        # todo should save in json, np.save() or something else
                    elif feature == "glcm":
                        pass
                        # todo should save in json, np.save() or something else
                    if should_bb:
                        img = self.make_square_with_bb(img)
                    if should_resize:
                        img = img.resize((416, 416))
                    os.makedirs(l_new, exist_ok=True)
                    img.save(p_new)
            else:
                paths[int(index)] = p_new
        df[feature] = paths
        df.to_csv(DATASET_PATH, index=False)
        return df

    def apply_feature(self, feature):
        pass

    def l_dirpath_from_row(self, row: pd.Series, feature: str):
        self.log.debug(f'path: {row["path"]}')
        l_name = str(row['path']).split(PATH_SEP)[-2]
        return self.dirpath_from_ft(feature) + l_name + PATH_SEP

    def path_from_row_ft(self, row: pd.Series, feature: str):
        f_name = str(row['path']).split(PATH_SEP)[-1]
        return self.l_dirpath_from_row(row, feature) + f_name

    def dirpath_from_ft(self, feature):
        if feature is None or feature == "":
            out_ft = "db"
        else:
            out_ft = feature
        return f"{self.save_path}_{out_ft}/"

    def _mk_ft_dirs(self):
        for feature in FTS:
            dir_new = self.dirpath_from_ft(feature)
            if not os.path.exists(dir_new):
                os.makedirs(dir_new)

    @staticmethod
    def lbp(img: Image, method="ror", radius=1):
        """Create Local Binary Pattern for an image
        @param img: image to convert
        @param method: which method, accepts 'default', 'ror', 'uniform', 'nri_uniform' or 'var'.
        Read skimage.feature.local_binary_pattern for more information
        @param radius: how many pixels adjacent to center pixel to calculate from.
        @return: (n, m) array as image
        """
        n_points = 8 * radius
        if img.mode != "L":
            img = img.convert("L")

        return np.array(local_binary_pattern(img, n_points, radius, method), dtype=np.uint8)

    @staticmethod
    def rlbp(img: Image, method="ror", radius=1):
        """Create RGB Local Binary Pattern for an image. Instead of greyscale, creates LBP for each RGB channel
        @param img: image to convert
        @param method: which method, accepts 'default', 'ror', 'uniform', 'nri_uniform' or 'var'.
        Read skimage.feature.local_binary_pattern for more information
        @param radius: how many pixels adjacent to center pixel to calculate from.
        @return: (n, m, 3) array as image
        """
        n_points = 8 * radius
        channels = [img.getchannel("R"), img.getchannel("G"), img.getchannel("B")]
        return (local_binary_pattern(ch, n_points, radius, method) for ch in channels)

    @staticmethod
    def glcm(img: Image, distance: list, angles: list):
        if angles is None:
            angles = range(0, 361, 45)
        if distance is None:
            distance = range(0, 5)
        if img.mode != "L":
            img = img.convert("L")
        return graycomatrix(img, distance, angles)

    @staticmethod
    def sift(img: Image.Image):
        sift_detector = SIFT()
        img = img.convert("L")
        sift_detector.detect_and_extract(img)
        print(sift_detector.keypoints)
        print(sift_detector.descriptors)
        for keypoint in sift_detector.keypoints:
            pass
        pass

    @staticmethod
    def make_square_with_bb(im, min_size=256, fill_color=(0, 0, 0, 0), mode="RGB"):
        x, y = im.size
        size = max(min_size, x, y)
        new_im = Image.new(mode, (size, size), fill_color)
        new_im.paste(im, (int((size - x) / 2), int((size - y) / 2)))
        return new_im

    @staticmethod
    def create_augmented_images(dir_path: str, degrees: str = "all"):
        """Creates transformed images from input image, can rotate and flip
        @param dir_path: path to species folder
        @param degrees: list of strings, include "rotate" to rotate, "flip" to flip, "all" is default for both
        """
        for sub_dir in os.walk(dir_path):
            for image_name in sub_dir[2]:
                if "all" == degrees:
                    for i in range(4):
                        FeatureExtractor.rotate_and_save_image(sub_dir[0], image_name, i * 90)
                        FeatureExtractor.flip_and_save_image(sub_dir[0],
                                                             f"{image_name.split('.')[0]}_{i * 90}.jpg")
                elif "rotate" == degrees:
                    for i in range(4):
                        FeatureExtractor.rotate_and_save_image(sub_dir[0], image_name, i * 90)
                elif "flip" == degrees:
                    FeatureExtractor.flip_and_save_image(sub_dir[0], image_name)


    @staticmethod
    def rotate_and_save_image(img_path: str, name: str, degree: int):
        """ Rotates an image 4 and saves the rotated images to a path
        @param img_path: path for where to store the newly created image
        @param name: name for the passed image
        @param degree: amount of degrees to rotate image
        """
        try:
            image = Image.open(f"{img_path}/{name}")
            image.rotate(degree, expand=True).save(f"{img_path}/{name.split('.')[0]}_{degree}.jpg")
        except IOError:
            print("Error when trying to rotate and save images")

    @staticmethod
    def flip_and_save_image(img_path: str, name: str):
        """ Flips an image and saves to a path
        @param img_path: path for where to store the newly created image
        @param name: name for the passed image
        """
        try:
            image = Image.open(f"{img_path}/{name}")
            image.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT).save(f"{img_path}/{name.split('.')[0]}f.jpg")
        except IOError:
            print("Error when trying to flip and save images")

    def feature_output_same_checker(self, feature: str, df):
        paths = df[feature]
        shape = np.array(Image.open(paths[0])).shape
        for path in paths:
            img = Image.open(path)
            arr = np.array(img)
            if(arr.shape != shape):
                return shape, False
        return shape, True
