import cv2
import numpy as np


class Perspective:
    r"""Convert perspective image to equirectangular image.
    Args:
        img_name (str or np.ndarray): The name of the image file or the image array.
        FOV (float): The field of view of the image in degrees.
        THETA (float): The left/right angle in degrees.
        PHI (float): The up/down angle in degrees.
        img_width (int): The width of the output equirectangular image.
        img_height (int): The height of the output equirectangular image.
        crop_bound (bool): Whether to crop the boundary area of the image proportionally.
    """
    def __init__(self, img_name=None, FOV=None, THETA=None, PHI=None, img_width=512, img_height=512, crop_bound=False):
        # either img_name is provided, or img_width/img_height and img in function GetEquirec is provided
        self.crop_bound = crop_bound
        if img_name is not None:
            # Load the image
            if isinstance(img_name, str):
                self._img = cv2.imread(img_name, cv2.IMREAD_COLOR)
            elif isinstance(img_name, np.ndarray):
                self._img = img_name
            [self._height, self._width, _] = self._img.shape
            # Crop the boundary area of the image proportionally
            if self.crop_bound:
                self._img = self._img[int(
                    self._height*0.05):int(self._height*0.95), int(self._width*0.05):int(self._width*0.95), :]

                [self._height, self._width, _] = self._img.shape
        else:
            self._img = None
            self._height = img_height
            self._width = img_width

        self.THETA = THETA
        self.PHI = PHI
        if self._width > self._height:
            self.wFOV = FOV
            self.hFOV = (float(self._height) / self._width) * FOV
        else:
            self.wFOV = (float(self._width) / self._height) * FOV
            self.hFOV = FOV

        self.w_len = np.tan(np.radians(self.wFOV / 2.0))
        self.h_len = np.tan(np.radians(self.hFOV / 2.0))

    def GetEquirec(self, height, width, img=None):
        #
        # THETA is left/right angle, PHI is up/down angle, both in degree
        #
        if self._img is None:
            self._img = img
        # Calculate the equirectangular coordinates
        x, y = np.meshgrid(np.linspace(-180, 180, width),
                           np.linspace(90, -90, height))
        # Convert spherical coordinates to Cartesian coordinates
        x_map = np.cos(np.radians(x)) * np.cos(np.radians(y))
        y_map = np.sin(np.radians(x)) * np.cos(np.radians(y))
        z_map = np.sin(np.radians(y))
        # Stack the coordinates to form a 3D array
        xyz = np.stack((x_map, y_map, z_map), axis=2)
        # Reshape the coordinates to match the image dimensions
        y_axis = np.array([0.0, 1.0, 0.0], np.float32)
        z_axis = np.array([0.0, 0.0, 1.0], np.float32)
        # Calculate the rotation matrices
        [R1, _] = cv2.Rodrigues(z_axis * np.radians(self.THETA))
        [R2, _] = cv2.Rodrigues(np.dot(R1, y_axis) * np.radians(-self.PHI))
        # Invert rotations to transform from equirectangular to perspective
        R1 = np.linalg.inv(R1)
        R2 = np.linalg.inv(R2)
        # Apply rotations
        xyz = xyz.reshape([height * width, 3]).T
        xyz = np.dot(R2, xyz)
        xyz = np.dot(R1, xyz).T
        xyz = xyz.reshape([height, width, 3])
        # Create mask for valid forward-facing points (x > 0)
        inverse_mask = np.where(xyz[:, :, 0] > 0, 1, 0)
        # Normalize coordinates by x-component (perspective division)
        xyz[:, :] = xyz[:, :] / \
            np.repeat(xyz[:, :, 0][:, :, np.newaxis], 3, axis=2)
        # Map 3D points back to 2D perspective image coordinates
        lon_map = np.where(
            (-self.w_len < xyz[:, :, 1]) & (xyz[:, :, 1] < self.w_len) \
                & (-self.h_len < xyz[:, :, 2]) & (xyz[:, :, 2] < self.h_len),
            (xyz[:, :, 1]+self.w_len)/2/self.w_len*self._width,
            0)
        lat_map = np.where(
            (-self.w_len < xyz[:, :, 1]) & (xyz[:, :, 1] < self.w_len) \
                & (-self.h_len < xyz[:, :, 2]) & (xyz[:, :, 2] < self.h_len),
            (-xyz[:, :, 2]+self.h_len) /
            2/self.h_len*self._height,
            0)
        mask = np.where(
            (-self.w_len < xyz[:, :, 1]) & (xyz[:, :, 1] < self.w_len) \
                & (-self.h_len < xyz[:, :, 2]) & (xyz[:, :, 2] < self.h_len),
            1,
            0)
        # Remap the image using the longitude and latitude maps
        persp = cv2.remap(self._img, lon_map.astype(np.float32), lat_map.astype(
            np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_WRAP)  # BORDER_CONSTANT) #))
        # Apply the mask to the equirectangular image
        mask = mask * inverse_mask
        mask = np.repeat(mask[:, :, np.newaxis], 3, axis=2)
        persp = persp * mask

        return persp, mask
