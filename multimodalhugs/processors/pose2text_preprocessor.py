import torch
import logging

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Union

from signwriting.tokenizer import normalize_signwriting
from signwriting.visualizer.visualize import signwriting_to_image

from transformers.feature_extraction_utils import BatchFeature, FeatureExtractionMixin
from transformers.image_utils import PILImageResampling  # If used in 'frame_preprocessor'
from transformers.processing_utils import ProcessorMixin

from multimodalhugs.data import (
    pad_and_create_mask,
    center_image_on_white_background,
)
from multimodalhugs.processors import MultimodalSecuence2TextTranslationProcessor
from pose_format import Pose
from pose_format.utils.generic import reduce_holistic, pose_hide_legs, pose_normalization_info

logger = logging.getLogger(__name__)


class Pose2TextTranslationProcessor(MultimodalSecuence2TextTranslationProcessor):  # FeatureExtractionMixin
    attributes = ["tokenizer"]
    model_input_names = ["input_frames", "attention_mask"]
    tokenizer_class = "AutoTokenizer"

    def __init__(
        self,
        tokenizer: Optional[Any] = None,
        reduce_holistic_poses: bool = True,
        **kwargs,
    ):
        self.reduce_holistic_poses = reduce_holistic_poses
        super().__init__(tokenizer=tokenizer, **kwargs)

    def _pose_file_to_tensor(self, pose_file: Union[str, Path]):
        with open(pose_file, "rb") as pose_file:
            pose = Pose.read(pose_file.read()) # [t, people, d, xyz]
        
        pose_hide_legs(pose)
    
        if self.reduce_holistic_poses:
            # This will be skipped if the pose is not holistic
            pose = reduce_holistic(pose) # [t, people, d', xyz]
        
        pose = pose.normalize(pose_normalization_info(pose.header))
        pose = pose.view(pose.size(0), -1)

        return pose.zero_filled()

    def _obtain_multimodal_input_and_masks(self, batch, **kwargs):
        tensor_secuences = [self._pose_file_to_tensor(sample["source"]) for sample in batch]
        padded_inputs, padded_input_masks = pad_and_create_mask(tensor_secuences)
        return {
            "inputs_embeds": padded_inputs,                         # torch.Size([batch_size, n_frames, n_channes, W, H])
            "attention_mask": padded_input_masks                   # torch.Size([batch_size, n_frames]) 0 indicates padding elements
        }, kwargs

