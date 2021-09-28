import os
import warnings
from typing import List

import numpy as np

from meerkat.columns.tensor_column import TensorColumn
from meerkat.datapanel import DataPanel
from meerkat.ml.activation import ActivationOp
from meerkat.tools.lazy_loader import LazyLoader

pl = LazyLoader("pytorch_lightning")


class ActivationCallback(pl.callbacks.Callback):
    def __init__(
        self,
        target_module: str,
        val_len: int,
        logdir: str,  # TODO(Priya): Use trainer.log_dir?
        mmap: bool = False,
    ):
        """Callback to store model activations during validation step

        Args:
            target_module (str): the name of the submodule of `model` (i.e. an
                intermediate layer) that outputs the activations we'd like to extract.
                For nested submodules, specify a path separated by "." (e.g.
                `ActivationCachedOp(model, "block4.conv")`).
            val_len (int): Number of inputs in the validation dataset
            logdir (str): Directory to store the activation datapanels
            mmap (bool): If true, activations are stored as memmapped numpy arrays
        """

        super().__init__()
        self.target_module = target_module
        self.val_len = val_len
        self.logdir = logdir
        self.mmap = mmap
        self.shape = None  # Shape of activations

        if self.mmap:
            warnings.warn(
                "Activations will be stored as numpy array when using memmapping."
            )

    def on_validation_epoch_start(self, trainer, pl_module):
        if not trainer.running_sanity_check:
            self.activation_op = ActivationOp(
                pl_module, self.target_module, pl_module.device
            )
            self.writer = TensorColumn.get_writer(mmap=self.mmap)

    def on_validation_batch_end(
        self, trainer, pl_module, outputs, batch, batch_idx, dataloader_idx
    ):
        # TODO(Priya): Check if skipping sanity check is fine
        if not trainer.running_sanity_check:
            activations = self.activation_op.extractor.activation.cpu().detach()

            # Use the first batch for setup
            if batch_idx == 0:
                if self.mmap:
                    shape = (self.val_len, *activations.shape[1:])
                    self.shape = shape

                    # TODO(Priya): File name format
                    file = f"activations_{self.target_module}_{trainer.current_epoch}"
                    self.writer.open(os.path.join(self.logdir, file), shape=shape)

                else:
                    self.writer.open()
            self.writer.write(activations)

    def on_validation_epoch_end(self, trainer, pl_module):
        if not trainer.running_sanity_check:
            activations = {f"activation_{self.target_module}": self.writer.flush()}
            activations = DataPanel.from_batch(activations)

            if not self.mmap:
                file = f"activations_{self.target_module}_{trainer.current_epoch}"
                activations.write(os.path.join(self.logdir, file))


def load_activations(
    target_module: str,
    logdir: str,
    epochs: List,
    mmap: bool = False,
    shape: tuple = None,
) -> DataPanel:

    if mmap and shape is None:
        raise ValueError(
            "Shape of activations is required to load memmapped activations."
        )

    activations_dp = None

    for epoch in epochs:
        path = os.path.join(logdir, f"activations_{target_module}_{epoch}")
        if not os.path.exists(path):
            raise ValueError(f"{path} does not exist.")

        if mmap:
            activations = np.memmap(path, mode="r", shape=shape)

            if activations_dp is None:
                activations_dp = DataPanel(
                    {f"activation_{target_module}_{epoch}": activations}
                )

            else:
                activations_dp.add_column(
                    f"activation_{target_module}_{epoch}", activations
                )

        else:
            if activations_dp is None:
                # TODO(Priya): How to rename column?
                activations_dp = DataPanel.read(path)

            else:
                activations_dp.add_column(
                    name=f"activation_{target_module}_{epoch}",
                    data=DataPanel.read(path)[f"activation_{target_module}"],
                )

    return activations_dp
